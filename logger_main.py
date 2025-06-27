# main.py
import logging
import config
from influx_handler import InfluxDBHandler
from mqtt_handler import MQTTHandler

def run_service():
    """Menginisialisasi dan menjalankan service logger."""
    
    # 1. Validasi konfigurasi terlebih dahulu
    if not config.validate_configs():
        logging.critical("Program berhenti karena konfigurasi tidak lengkap.")
        return

    # 2. Inisialisasi handler InfluxDB
    try:
        influx_db = InfluxDBHandler()
    except Exception:
        logging.critical("Gagal menginisialisasi InfluxDB Handler. Program berhenti.")
        return

    # 3. Inisialisasi handler MQTT dan berikan handler InfluxDB
    # Ini disebut Dependency Injection, sebuah praktik yang sangat baik.
    mqtt_service = MQTTHandler(influx_handler=influx_db)
    
    # 4. Jalankan service MQTT
    mqtt_service.start()


if __name__ == "__main__":
    config.logging.info("Memulai Logger Service Kualitas Udara...")
    run_service()