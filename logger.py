import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os
import logging
from dotenv import load_dotenv
from datetime import datetime, timezone

# --- 1. Konfigurasi Awal & Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
load_dotenv()

# --- 2. Memuat Konfigurasi dari Environment ---
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")
INFLUX_URL = os.getenv("INFLUX_URL")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_DATA = os.getenv("MQTT_TOPIC_DATA")
MQTT_CLIENT_ID_LOGGER = "python-logger-kualitas-udara-final"

# Validasi variabel environment
required_vars = ["INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET", "INFLUX_URL", "MQTT_BROKER", "MQTT_TOPIC_DATA"]
for var in required_vars:
    if not globals()[var]:
        logging.critical(f"Error: Environment variable {var} tidak ditemukan. Pastikan file .env ada dan benar.")
        exit()

# --- 3. Fungsi-fungsi Inti ---
def on_connect(client, userdata, flags, rc):
    """Callback saat terhubung ke MQTT Broker."""
    if rc == 0:
        logging.info("Berhasil terhubung ke MQTT Broker!")
        client.subscribe(MQTT_TOPIC_DATA)
        logging.info(f"Berlangganan ke topik: {MQTT_TOPIC_DATA}")
    else:
        logging.error(f"Gagal terhubung ke MQTT, kode hasil: {rc}")

def on_message(client, userdata, msg):
    """Callback saat pesan diterima dari MQTT."""
    logging.info(f"Pesan diterima pada topik {msg.topic}")
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        logging.info(f"Data JSON diterima: {data}")

        if 'gas_ppm' not in data or 'timestamp' not in data:
            logging.warning("Peringatan: 'gas_ppm' atau 'timestamp' tidak ada dalam payload. Pesan dilewati.")
            return

        device_timestamp = datetime.fromtimestamp(int(data["timestamp"]), tz=timezone.utc)

        point = Point("pengukuran_udara") \
            .tag("id_alat", "ALAT_01") \
            .field("suhu", float(data.get("suhu", 0.0))) \
            .field("kelembaban", float(data.get("kelembaban", 0.0))) \
            .field("tekanan", float(data.get("tekanan", 0.0))) \
            .field("gas_ppm", float(data["gas_ppm"])) \
            .time(device_timestamp)

        write_api = userdata['write_api']
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        logging.info("Data berhasil disimpan ke InfluxDB.")

    except json.JSONDecodeError:
        logging.error("Gagal men-decode JSON. Payload mungkin tidak valid.")
    except (KeyError, TypeError) as e:
        logging.error(f"Error pada data JSON (kunci atau tipe data salah): {e}")
    except Exception as e:
        logging.error(f"Terjadi error yang tidak terduga: {e}", exc_info=True)

def main():
    """Fungsi utama untuk menjalankan logger."""
    try:
        logging.info("Menginisialisasi klien InfluxDB...")
        influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=10_000)
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        logging.info("Klien InfluxDB siap.")
    except Exception as e:
        logging.critical(f"Tidak dapat terhubung ke InfluxDB: {e}")
        return

    user_data = {'write_api': write_api}
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID_LOGGER, protocol=mqtt.MQTTv311)
    mqtt_client.user_data_set(user_data)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        logging.info(f"Menghubungkan ke MQTT Broker di {MQTT_BROKER}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logging.critical(f"Tidak dapat terhubung ke MQTT Broker: {e}")
        return

    logging.info("Logger Service berjalan. Menunggu data...")
    mqtt_client.loop_forever()

# --- 4. Titik Masuk Program ---
if __name__ == "__main__":
    main()