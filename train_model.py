import pandas as pd
import numpy as np
from influxdb_client import InfluxDBClient
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
import joblib
import os
from dotenv import load_dotenv
import logging
import json

# --- 1. Konfigurasi Awal & Logging ---
# Mengkonfigurasi format logging yang lebih informatif
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Memuat variabel dari file .env
load_dotenv()

# --- 2. Memuat Konfigurasi dari Environment ---
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_URL = os.getenv("INFLUX_URL")

# Variabel konfigurasi training, bisa diubah di sini
DATA_RANGE = "-3h"  # Rentang waktu data yang akan diambil (contoh: "-30d", "-7d", "-3d")
MODEL_FILENAME = "model_prediksi_gas_terbaik.keras"
SCALER_FILENAME = "scaler.pkl"
CONFIG_FILENAME = "model_config.json"

# Validasi variabel environment
for var in ["INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET", "INFLUX_URL"]:
    if not globals()[var]:
        logging.critical(f"Error: Environment variable {var} tidak ditemukan. Pastikan file .env ada dan benar.")
        exit()

# --- 3. Fungsi-fungsi Helper ---

def fetch_data():
    """Mengambil data dari InfluxDB dan mengembalikannya sebagai DataFrame."""
    logging.info(f"Menghubungkan ke InfluxDB untuk mengambil data rentang {DATA_RANGE}...")
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {DATA_RANGE})
      |> filter(fn: (r) => r["_measurement"] == "pengukuran_udara")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> drop(columns: ["_start", "_stop", "id_alat", "_measurement"])
    '''
    try:
        df = query_api.query_data_frame(query=query)
        logging.info(f"Total {len(df)} data point berhasil diambil.")
        return df
    except Exception as e:
        logging.error(f"Gagal mengambil data dari InfluxDB: {e}")
        return pd.DataFrame()

def preprocess_data(df):
    """Melakukan pra-pemrosesan dan feature engineering."""
    if df.empty: return None
    logging.info("Melakukan pra-pemrosesan data...")
    
    # Hapus kolom 'result' yang terkadang muncul dari query pivot
    if 'result' in df.columns:
        df = df.drop(columns=['result'])
        
    df.set_index('_time', inplace=True)
    df.index = pd.to_datetime(df.index)
    
    numeric_cols = ['suhu', 'kelembaban', 'tekanan', 'gas_ppm']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Resample data ke interval 5 menit dan hitung rata-rata HANYA untuk kolom numerik
    df = df.resample('5min').mean(numeric_only=True) 
    df.interpolate(method='time', inplace=True)
    df.dropna(inplace=True)

    # Encoding fitur waktu menjadi siklikal untuk pemahaman model yang lebih baik
    df['jam_sin'] = np.sin(2 * np.pi * df.index.hour/24.0)
    df['jam_cos'] = np.cos(2 * np.pi * df.index.hour/24.0)
    df['hari_minggu_sin'] = np.sin(2 * np.pi * df.index.dayofweek/7.0)
    df['hari_minggu_cos'] = np.cos(2 * np.pi * df.index.dayofweek/7.0)
    
    return df

def create_sequences(data, n_steps, target_idx):
    """Membuat sekuens data untuk model LSTM."""
    X, y = [], []
    for i in range(len(data) - n_steps):
        X.append(data[i:(i + n_steps), :])
        y.append(data[i + n_steps, target_idx])
    return np.array(X), np.array(y)

# --- 4. Fungsi Utama Pelatihan Model ---

def train_and_save_model():
    """Orkestrasi seluruh proses: fetch, preprocess, train, dan save."""
    df_raw = fetch_data()
    df = preprocess_data(df_raw)

    if df is None or df.empty:
        logging.error("Tidak ada data untuk dilatih. Proses dihentikan.")
        return

    # Persiapan Fitur & Target
    features = ['suhu', 'kelembaban', 'tekanan', 'gas_ppm', 'jam_sin', 'jam_cos', 'hari_minggu_sin', 'hari_minggu_cos']
    target_col = 'gas_ppm'
    
    if not all(col in df.columns for col in features):
        missing_cols = [col for col in features if col not in df.columns]
        logging.error(f"Satu atau lebih kolom fitur tidak ditemukan di data: {missing_cols}")
        return

    # Normalisasi & Pemisahan Data Kronologis
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(df[features])
    
    train_size = int(len(scaled_data) * 0.8)
    train_data = scaled_data[:train_size]
    val_data = scaled_data[train_size:]
    
    n_steps = 24  # Melihat data 2 jam ke belakang (24 * 5 menit)
    
    if len(train_data) < n_steps + 1 or len(val_data) < n_steps + 1:
        logging.error(f"Data tidak cukup ({len(df)} baris) untuk membuat sekuens training/validasi. Coba ambil data dengan rentang waktu lebih lama.")
        return
    
    target_idx = features.index(target_col)
    X_train, y_train = create_sequences(train_data, n_steps, target_idx)
    X_val, y_val = create_sequences(val_data, n_steps, target_idx)
    logging.info(f"Bentuk data training: X={X_train.shape}, y={y_train.shape}")
    logging.info(f"Bentuk data validasi: X={X_val.shape}, y={y_val.shape}")

    # Membangun, Melatih & Validasi Model
    logging.info("Membangun dan melatih model AI...")
    n_features = X_train.shape[2]
    
    model = Sequential([
        LSTM(50, activation='tanh', return_sequences=True, input_shape=(n_steps, n_features)),
        Dropout(0.2),
        LSTM(50, activation='tanh'),
        Dropout(0.2),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.summary()
    
    # Menggunakan Callbacks untuk training yang lebih efisien
    checkpoint_cb = ModelCheckpoint(MODEL_FILENAME, save_best_only=True, monitor='val_loss', mode='min')
    early_stopping_cb = EarlyStopping(patience=10, restore_best_weights=True, monitor='val_loss', mode='min')
    
    model.fit(X_train, y_train, epochs=100, batch_size=32, verbose=1, 
              validation_data=(X_val, y_val), 
              callbacks=[checkpoint_cb, early_stopping_cb])

    # Menyimpan Artefak
    logging.info("Menyimpan scaler dan konfigurasi model...")
    joblib.dump(scaler, SCALER_FILENAME)
    
    model_config = {
        'n_steps': n_steps,
        'features': features
    }
    with open(CONFIG_FILENAME, 'w') as f:
        json.dump(model_config, f, indent=4)

    logging.info(f"Pelatihan selesai! Artefak ('{MODEL_FILENAME}', '{SCALER_FILENAME}', '{CONFIG_FILENAME}') telah dibuat.")

# --- 5. Titik Masuk Program ---
if __name__ == "__main__":
    train_and_save_model()