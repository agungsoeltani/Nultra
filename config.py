import os
import logging
from dotenv import load_dotenv

load_dotenv()

# --- Konfigurasi Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Konfigurasi InfluxDB ---
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_URL = os.getenv("INFLUX_URL")

# --- Konfigurasi MQTT ---
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_DATA = os.getenv("MQTT_TOPIC_DATA")
MQTT_CLIENT_ID_LOGGER = "python-logger-kualitas-udara-final"


def validate_configs():
    """Memvalidasi bahwa semua variabel environment yang dibutuhkan telah di-set."""
    required_vars = [
        "INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET", "INFLUX_URL",
        "MQTT_BROKER", "MQTT_TOPIC_DATA"
    ]
    for var in required_vars:
        if not globals()[var]:
            logging.critical(f"Error: Environment variable {var} tidak ditemukan.")
            return False
    return True