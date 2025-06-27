import logging
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
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
            device_timestamp = datetime.fromtimestamp(int(data["timestamp"]), tz=timezone.utc)

            point = Point("pengukuran_udara") \
                .tag("id_alat", data.get("id_alat", "ALAT_01")) \
                .field("suhu", float(data.get("suhu", 0.0))) \
                .field("kelembaban", float(data.get("kelembaban", 0.0))) \
                .field("tekanan", float(data.get("tekanan", 0.0))) \
                .field("gas_ppm", float(data["gas_ppm"])) \
                .time(device_timestamp)

            self.write_api.write(bucket=config.INFLUX_BUCKET, org=config.INFLUX_ORG, record=point)
            logging.info(f"Data point untuk id_alat '{point.tags['id_alat']}' berhasil disimpan.")
            return True
        except (KeyError, TypeError) as e:
            logging.error(f"Error pada data JSON (kunci atau tipe data salah): {e}")
        except InfluxDBError as e:
            logging.error(f"Error saat menulis ke InfluxDB: {e}")
        except Exception as e:
            logging.error(f"Terjadi error tak terduga saat memproses data untuk InfluxDB: {e}")
        return False