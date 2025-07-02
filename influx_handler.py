import logging
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
from dateutil import parser  # Untuk parsing timestamp string
import config

class InfluxDBHandler:
    def __init__(self):
        try:
            self.client = InfluxDBClient(
                url=config.INFLUX_URL,
                token=config.INFLUX_TOKEN,
                org=config.INFLUX_ORG,
                timeout=10_000
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logging.info("Klien InfluxDB berhasil diinisialisasi.")
        except Exception as e:
            logging.critical(f"Tidak dapat membuat klien InfluxDB: {e}")
            raise  # Melempar exception agar program berhenti

    def write_data(self, data: dict):
        """Memformat dan menulis data yang diterima ke InfluxDB."""
        try:
            # Debug: log data mentah
            logging.debug(f"Data diterima: {data}")

            # Parsing timestamp, mendukung string dan angka
            raw_timestamp = data.get("timestamp")
            if isinstance(raw_timestamp, str):
                device_timestamp = parser.parse(raw_timestamp).astimezone(timezone.utc)
            else:
                device_timestamp = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc)

            # Mengambil id_alat dari data payload untuk digunakan di logging
            id_alat = data.get("id_alat", "ALAT_01")

            point = Point("pengukuran_udara") \
                .tag("id_alat", id_alat) \
                .field("suhu", float(data.get("suhu", 0.0))) \
                .field("kelembaban", float(data.get("kelembaban", 0.0))) \
                .field("tekanan", float(data.get("tekanan", 0.0))) \
                .field("gas_ppm", float(data.get("gas_ppm", 0.0))) \
                .time(device_timestamp)

            self.write_api.write(bucket=config.INFLUX_BUCKET, org=config.INFLUX_ORG, record=point)
            logging.info(f"Data point untuk id_alat '{id_alat}' berhasil disimpan.")
            return True

        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"Error pada data JSON (kunci atau tipe data salah): {e}")
        except InfluxDBError as e:
            logging.error(f"Error saat menulis ke InfluxDB: {e}")
        except Exception as e:
            logging.error(f"Terjadi error tak terduga saat memproses data untuk InfluxDB: {e}")
        return False
