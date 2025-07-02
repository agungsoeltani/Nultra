import pandas as pd
import numpy as np
from influxdb_client import InfluxDBClient
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
import joblib
import os
from dotenv import load_dotenv
import logging
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --- 1. Konfigurasi Awal & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- 2. Path Artefak dan Konfigurasi ---
MODEL_PATH = 'model_prediksi_gas.h5' # Ganti ke .keras jika Anda sudah mengubahnya
SCALER_PATH = 'scaler.pkl'
CONFIG_PATH = 'model_config.json'
OUTPUT_PLOT_PATH = 'prediction_vs_actual.png'

# --- 3. Fungsi-fungsi Helper (Sama seperti di training) ---

def fetch_data():
    """Mengambil data dari InfluxDB."""
    INFLUX_URL = os.getenv("INFLUX_URL")
    INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
    INFLUX_ORG = os.getenv("INFLUX_ORG")
    INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
    
    logging.info("Menghubungkan ke InfluxDB untuk mengambil data...")
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "pengukuran_udara")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> drop(columns: ["_start", "_stop", "id_alat", "_measurement"])
    '''
    try:
        df = query_api.query_dframe(query=query)
        logging.info(f"Total {len(df)} data point berhasil diambil.")
        return df
    except Exception as e:
        logging.error(f"Gagal mengambil data dari InfluxDB: {e}")
        return pd.DataFrame()

def preprocess_data(df):
    """Melakukan pra-pemrosesan pada DataFrame."""
    if df.empty: return None
    logging.info("Melakukan pra-pemrosesan data...")
    df.set_index('_time', inplace=True)
    df.index = pd.to_datetime(df.index)
    
    numeric_cols = ['suhu', 'kelembaban', 'tekanan', 'gas_ppm']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.resample('5T').mean()
    df.interpolate(method='time', inplace=True)
    df.dropna(inplace=True)

    df['jam_sin'] = np.sin(2 * np.pi * df.index.hour/24.0)
    df['jam_cos'] = np.cos(2 * np.pi * df.index.hour/24.0)
    df['hari_minggu_sin'] = np.sin(2 * np.pi * df.index.dayofweek/7.0)
    df['hari_minggu_cos'] = np.cos(2 * np.pi * df.index.dayofweek/7.0)
    
    return df

def create_sequences(data, n_steps):
    """Membuat sekuens HANYA untuk input (X)."""
    X = []
    for i in range(len(data) - n_steps):
        X.append(data[i:(i + n_steps), :])
    return np.array(X)

# --- 4. Fungsi Utama Prediksi & Visualisasi ---

def predict_and_plot():
    """Fungsi utama untuk memuat model, membuat prediksi, dan memvisualisasikan hasilnya."""
    
    # --- Memuat Artefak ---
    try:
        logging.info(f"Memuat model dari {MODEL_PATH}...")
        model = load_model(MODEL_PATH)
        
        logging.info(f"Memuat scaler dari {SCALER_PATH}...")
        scaler = joblib.load(SCALER_PATH)
        
        logging.info(f"Memuat konfigurasi dari {CONFIG_PATH}...")
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        n_steps = config['n_steps']
        features = config['features']
    except FileNotFoundError as e:
        logging.critical(f"Error: File artefak tidak ditemukan - {e}. Pastikan Anda sudah menjalankan skrip training.")
        return

    # --- Ambil dan Proses Data ---
    df_raw = fetch_data()
    df_processed = preprocess_data(df_raw)
    
    if df_processed is None or df_processed.empty:
        logging.error("Tidak ada data untuk diprediksi.")
        return

    # --- Persiapan Data untuk Prediksi ---
    # Pastikan urutan kolom sama persis seperti saat training
    df_ordered = df_processed[features]
    
    # Gunakan scaler yang SUDAH di-fit untuk mentransformasi data
    scaled_data = scaler.transform(df_ordered)
    
    # Buat sekuens dari seluruh data
    X_full = create_sequences(scaled_data, n_steps)
    
    # --- Membuat Prediksi ---
    logging.info("Membuat prediksi dengan model...")
    predictions_scaled = model.predict(X_full)
    
    # --- Mengembalikan Hasil ke Skala Asli (Inverse Transform) ---
    logging.info("Mengembalikan hasil prediksi ke skala PPM asli...")
    # Buat array dummy untuk inverse transform, karena scaler dilatih pada banyak fitur
    dummy_array = np.zeros((len(predictions_scaled), len(features)))
    # Masukkan prediksi ke kolom yang sesuai (kolom target 'gas_ppm')
    target_idx = features.index('gas_ppm')
    dummy_array[:, target_idx] = predictions_scaled.ravel()
    
    # Lakukan inverse transform
    predictions_unscaled = scaler.inverse_transform(dummy_array)[:, target_idx]
    
    # --- Menyiapkan Data untuk Plot ---
    # Kita perlu data aktual untuk dibandingkan. Kita ambil dari DataFrame asli.
    # Prediksi dimulai dari indeks ke-n_steps
    actual_values = df_ordered['gas_ppm'].values[n_steps:]
    timestamps = df_ordered.index[n_steps:]
    
    # --- Membuat dan Menyimpan Plot ---
    logging.info(f"Membuat plot perbandingan dan menyimpannya ke {OUTPUT_PLOT_PATH}...")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(15, 7))
    
    ax.plot(timestamps, actual_values, label='Data Aktual (PPM)', color='darkorange', marker='.', linestyle='-')
    ax.plot(timestamps, predictions_unscaled, label='Prediksi Model (PPM)', color='dodgerblue', linestyle='--')
    
    ax.set_title('Perbandingan Data Gas PPM Aktual vs Prediksi Model', fontsize=16)
    ax.set_xlabel('Waktu', fontsize=12)
    ax.set_ylabel('Konsentrasi Gas (PPM)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True)
    
    # Format tanggal di sumbu-x agar lebih mudah dibaca
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %H:%M'))
    fig.autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT_PATH)
    logging.info("Plot berhasil disimpan.")
    plt.show()

# --- 5. Titik Masuk Program ---
if __name__ == "__main__":
    predict_and_plot()