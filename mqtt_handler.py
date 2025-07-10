# mqtt_handler.py
#testing runner 

import paho.mqtt.client as mqtt
import logging
import json
import os
import socket
import config  # pastikan file config.py berisi info broker lokal, port, dan topik

class MQTTHandler:
    def __init__(self, influx_handler):
        self.influx_handler = influx_handler

        # Koneksi MQTT ke broker lokal tanpa WebSocket
        self.client = mqtt.Client(
            client_id=config.MQTT_CLIENT_ID_LOGGER,
            protocol=mqtt.MQTTv311  # MQTT versi standar untuk koneksi lokal
        )
        logging.info("MQTT Client diinisialisasi dengan koneksi TCP biasa.")

        # Jika kamu tetap pakai username/password
        mqtt_user = os.getenv("MQTT_USER")
        mqtt_pass = os.getenv("MQTT_PASS")
        if mqtt_user and mqtt_pass:
            self.client.username_pw_set(mqtt_user, mqtt_pass)
            logging.info("Kredensial MQTT (username/password) telah diatur.")
        else:
            logging.warning("Tidak menggunakan autentikasi MQTT (koneksi anonim).")

        # Callback
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        conn_str = mqtt.connack_string(rc)
        if rc == 0:
            logging.info(f"✅ Berhasil terhubung ke MQTT Broker! ({conn_str})")
            client.subscribe(config.MQTT_TOPIC_DATA)
            logging.info(f"📡 Berhasil subscribe ke topik: {config.MQTT_TOPIC_DATA}")
        else:
            logging.error(f"❌ Gagal konek MQTT. Kode: {rc}, Pesan: {conn_str}")

    def _on_message(self, client, userdata, msg):
        logging.info(f"📨 Pesan diterima dari topik: {msg.topic}")
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            logging.debug(f"📦 Payload JSON: {data}")

            if 'gas_ppm' not in data or 'timestamp' not in data:
                logging.warning(f"⚠️ Data tidak valid. Payload: {payload}")
                return

            self.influx_handler.write_data(data)
            logging.info("✅ Data berhasil dikirim ke InfluxDB.")

        except json.JSONDecodeError:
            logging.error(f"❌ Payload bukan JSON valid: {msg.payload.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logging.error(f"⚠️ Error saat proses pesan MQTT: {e}", exc_info=True)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logging.warning(f"🔌 Koneksi MQTT terputus secara tak terduga: {rc}")
        else:
            logging.info("🔌 Koneksi MQTT ditutup dengan normal.")

    def start(self):
        try:
            logging.info(f"🚀 Menghubungkan ke MQTT broker {config.MQTT_BROKER}:{config.MQTT_PORT}...")
            self.client.connect(
                host=config.MQTT_BROKER,
                port=config.MQTT_PORT,
                keepalive=60
            )
            self.client.loop_forever()

        except socket.gaierror:
            logging.critical(f"🔥 Gagal konek: DNS error untuk host '{config.MQTT_BROKER}'")
        except ConnectionRefusedError:
            logging.critical(f"🔥 Gagal konek: koneksi ditolak. Cek apakah broker MQTT berjalan.")
        except TimeoutError:
            logging.critical(f"🔥 Timeout koneksi ke broker MQTT.")
        except Exception as e:
            logging.critical(f"🔥 Error fatal saat koneksi MQTT: {e}", exc_info=True)
