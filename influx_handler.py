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
            logging.info("✅ Klien InfluxDB berhasil diinisialisasi.")
        except Exception as e:
            logging.critical(f"❌ Gagal menginisialisasi klien InfluxDB. Periksa URL, token, atau org. Detail: {e}")
            raise  # Program dihentikan jika tidak bisa konek ke InfluxDB

    def write_data(self, data: dict):
        """Memformat dan menulis data yang diterima ke InfluxDB."""
        try:
            # Debug: log data mentah
            logging.debug(f"📦 Payload mentah diterima: {data}")

            # Validasi timestamp
            raw_timestamp = data.get("timestamp")
            if raw_timestamp is None:
                raise ValueError("Field 'timestamp' tidak ditemukan dalam data.")

            # Parsing timestamp (string atau angka)
            if isinstance(raw_timestamp, str):
                device_timestamp = parser.parse(raw_timestamp).astimezone(timezone.utc)
                logging.debug(f"🕒 Timestamp string berhasil di-parse: {device_timestamp.isoformat()}")
            else:
                device_timestamp = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc)
                logging.debug(f"🕒 Timestamp integer berhasil diubah: {device_timestamp.isoformat()}")

            id_alat = data.get("id_alat", "ALAT_01")

            # Membuat data point
            point = Point("pengukuran_udara") \
                .tag("id_alat", id_alat) \
                .field("suhu", float(data.get("suhu", 0.0))) \
                .field("kelembaban", float(data.get("kelembaban", 0.0))) \
                .field("tekanan", float(data.get("tekanan", 0.0))) \
                .field("gas_ppm", float(data.get("gas_ppm", 0.0))) \
                .time(device_timestamp)

            # Menulis ke InfluxDB
            self.write_api.write(bucket=config.INFLUX_BUCKET, org=config.INFLUX_ORG, record=point)
            logging.info(f"✅ Data berhasil dikirim ke InfluxDB untuk id_alat '{id_alat}' pada waktu {device_timestamp.isoformat()}")
            return True

        except KeyError as e:
            logging.error(f"❌ KeyError: Field wajib hilang dalam data: {e}")
        except TypeError as e:
            logging.error(f"❌ TypeError: Format tipe data tidak sesuai: {e}")
        except ValueError as e:
            logging.error(f"❌ ValueError: Nilai tidak valid: {e}")
        except InfluxDBError as e:
            logging.error(f"❌ InfluxDBError: Gagal menulis ke InfluxDB. Periksa organisasi, bucket, atau field. Detail: {e}")
        except Exception as e:
            logging.error(f"❌ Exception tak terduga saat memproses data InfluxDB: {e}")
        
        return False
