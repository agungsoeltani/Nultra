# config.py

import os
import logging
from dotenv import load_dotenv

# Muat variabel dari file .env di direktori yang sama
load_dotenv()

# --- Konfigurasi Logging ---
# Konfigurasi ini akan diaplikasikan saat modul ini diimpor pertama kali.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Konfigurasi InfluxDB ---
# (Tidak ada perubahan di sini, sudah bagus)
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_URL = os.getenv("INFLUX_URL")

# --- Konfigurasi MQTT (Disesuaikan untuk Cloudflare WSS) ---
MQTT_BROKER = os.getenv("MQTT_BROKER")

# ## DIUBAH ##: Default port diubah ke 443 untuk koneksi WSS (WebSocket Secure)
MQTT_PORT = int(os.getenv("MQTT_PORT", 443)) 

# ## BARU ##: Menambahkan variabel untuk WebSocket Path. Krusial untuk koneksi WSS.
# Defaultnya adalah "/mqtt", yang sesuai untuk EMQX dan Mosquitto.
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt") 

MQTT_TOPIC_DATA = os.getenv("MQTT_TOPIC_DATA")
MQTT_CLIENT_ID_LOGGER = "python-logger-kualitas-udara-final"


def validate_configs():
    """
    Memvalidasi bahwa semua variabel environment yang dibutuhkan telah di-set.
    Fungsi ini akan menghentikan program jika ada konfigurasi yang hilang.
    """
    logging.info("Memvalidasi konfigurasi environment...")
    
    # ## DIUBAH ##: Menambahkan variabel baru ke daftar validasi
    required_vars = {
        "INFLUX_TOKEN": INFLUX_TOKEN,
        "INFLUX_ORG": INFLUX_ORG,
        "INFLUX_BUCKET": INFLUX_BUCKET,
        "INFLUX_URL": INFLUX_URL,
        "MQTT_BROKER": MQTT_BROKER,
        "MQTT_PORT": MQTT_PORT,
        "MQTT_WS_PATH": MQTT_WS_PATH,
        "MQTT_TOPIC_DATA": MQTT_TOPIC_DATA
    }
    
    missing_vars = [var_name for var_name, value in required_vars.items() if not value]
    
    if missing_vars:
        for var in missing_vars:
            logging.critical(f"❌ FATAL: Environment variable '{var}' tidak ditemukan atau kosong. Harap set di file .env Anda.")
        # Menghentikan eksekusi jika ada variabel penting yang hilang
        exit("Program dihentikan karena konfigurasi tidak lengkap.")
        return False
        
    logging.info("✅ Semua konfigurasi yang dibutuhkan telah ditemukan.")
    return True

# Panggil fungsi validasi saat modul ini dijalankan atau diimpor
# agar program langsung berhenti jika ada yang salah.
validate_configs()