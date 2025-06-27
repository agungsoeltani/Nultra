import pandas as pd
import numpy as np
from influxdb_client import InfluxDBClient
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import joblib
import os
from dotenv import load_dotenv
import logging

# --- 1. Konfigurasi Awal & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- 2. Memuat Konfigurasi dari Environment ---
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_URL = os.getenv("INFLUX_URL")

# Validasi variabel environment
for var in ["INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET", "INFLUX_URL"]:
    if not globals()[var]:
        logging.critical(f"Error: Environment variable {var} tidak ditemukan. Pastikan file .env ada dan benar.")
        exit()

# --- 3. Fungsi-fungsi Helper ---

def fetch_data():
    """Mengambil data dari InfluxDB dan mengembalikannya sebagai DataFrame."""
    logging.info("Menghubungkan ke InfluxDB untuk mengambil data...")
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    # Query untuk mengambil data 30 hari terakhir dan memformatnya
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "pengukuran_udara")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueKey: "_value")
      |> drop(columns: ["_start", "_stop", "id_alat", "_measurement"])
    '''
    try:
        df = query_api.query_dframe(query=query)
        logging.info(f"Total {len(df)} data point berhasil diambil.")
        return df
    except Exception as e:
        logging.error(f"Gagal mengambil data dari InfluxDB: {e}")
        return pd.DataFrame() # Mengembalikan DataFrame kosong jika gagal

def preprocess_data(df):
    """Melakukan pra-pemrosesan pada DataFrame."""
    if df.empty:
        return None
    logging.info("Melakukan pra-pemrosesan data...")
    df.set_index('_time', inplace=True)
    df.index = pd.to_datetime(df.index)
    
    # PERBAIKAN: Menggunakan gas_ppm
    # Memastikan semua kolom numerik sebelum interpolasi
    numeric_cols = ['suhu', 'kelembaban', 'tekanan', 'gas_ppm']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.interpolate(method='time', inplace=True)
    df.dropna(inplace=True) # Hapus baris yang masih memiliki NaN setelah interpolasi

    # Feature Engineering: Menambahkan fitur berbasis waktu
    df['jam'] = df.index.hour
    df['hari_minggu'] = df.index.dayofweek
    return df

def create_sequences(data, features, n_steps, target_col):
    """Membuat sekuens data untuk model LSTM."""
    X, y = [], []
    target_idx = features.index(target_col)
    
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

    # --- PERSIAPAN SEKUEN ---
    logging.info("Mempersiapkan sekuens untuk model...")
    
    # PERBAIKAN: Menggunakan 'gas_ppm' bukan 'nilai_gas'
    features = ['suhu', 'kelembaban', 'tekanan', 'gas_ppm', 'jam', 'hari_minggu']
    target_col = 'gas_ppm' 
    
    # Pastikan semua kolom yang dibutuhkan ada
    if not all(col in df.columns for col in features):
        logging.error(f"Satu atau lebih kolom fitur tidak ditemukan di data: {features}")
        return

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(df[features])

    n_steps = 24  # Melihat data 24 langkah ke belakang (misal: 24 menit)
    
    # Validasi jumlah data
    if len(scaled_data) < n_steps + 1:
        logging.error(f"Data tidak cukup ({len(scaled_data)} baris) untuk membuat sekuens dengan n_steps={n_steps}.")
        return

    X, y = create_sequences(scaled_data, features, n_steps, target_col)
    logging.info(f"Bentuk data training: X={X.shape}, y={y.shape}")

    # --- MEMBANGUN & MELATIH MODEL ---
    logging.info("Membangun dan melatih model AI...")
    n_features = X.shape[2]
    
    model = Sequential([
        LSTM(50, activation='tanh', return_sequences=True, input_shape=(n_steps, n_features)),
        Dropout(0.2),
        LSTM(50, activation='tanh'),
        Dropout(0.2),
        Dense(1)
    ])
    # Menggunakan tanh (standar untuk LSTM) bisa memberikan hasil lebih baik daripada relu
    
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.summary()
    
    # Melatih model
    model.fit(X, y, epochs=50, batch_size=32, verbose=1, validation_split=0.1)

    # --- SIMPAN MODEL & SCALER ---
    logging.info("Menyimpan model dan scaler...")
    model.save('model_prediksi_gas.h5')
    joblib.dump(scaler, 'scaler.pkl')

    logging.info("Pelatihan selesai! File 'model_prediksi_gas.h5' dan 'scaler.pkl' telah dibuat.")

# --- 5. Titik Masuk Program ---
if __name__ == "__main__":
    train_and_save_model()