import paho.mqtt.client as mqtt
import logging
import json
import config
from influx_handler import InfluxDBHandler

class MQTTHandler:
    def __init__(self, influx_handler: InfluxDBHandler):
        self.influx_handler = influx_handler
        self.client = mqtt.Client(client_id=config.MQTT_CLIENT_ID_LOGGER, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Berhasil terhubung ke MQTT Broker!")
            client.subscribe(config.MQTT_TOPIC_DATA)
            logging.info(f"Berlangganan ke topik: {config.MQTT_TOPIC_DATA}")
        else:
            logging.error(f"Gagal terhubung ke MQTT, kode hasil: {rc}")

    def _on_message(self, client, userdata, msg):
        logging.info(f"Pesan diterima pada topik {msg.topic}")
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            logging.info(f"Data JSON diterima: {data}")

            # Validasi data penting
            if 'gas_ppm' not in data or 'timestamp' not in data:
                logging.warning("Peringatan: 'gas_ppm' atau 'timestamp' tidak ada. Pesan dilewati.")
                return
            
            # Melempar tanggung jawab penulisan ke InfluxDB handler
            self.influx_handler.write_data(data)

        except json.JSONDecodeError:
            logging.error("Gagal men-decode JSON. Payload mungkin tidak valid.")
        except Exception as e:
            logging.error(f"Error tak terduga di on_message: {e}", exc_info=True)

    def start(self):
        """Menghubungkan ke broker dan memulai loop selamanya."""
        try:
            logging.info(f"Menghubungkan ke MQTT Broker di {config.MQTT_BROKER}...")
            self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
            logging.info("Logger Service berjalan. Menunggu data...")
            self.client.loop_forever()
        except Exception as e:
            logging.critical(f"Tidak dapat terhubung ke MQTT Broker: {e}")