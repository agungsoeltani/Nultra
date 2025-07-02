# mqtt_handler.py

import paho.mqtt.client as mqtt
import logging
import json
import os
import ssl
import socket  # Diimpor untuk menangani error DNS
import config  # Pastikan file config.py ada di direktori yang sama

# Asumsikan Anda memiliki InfluxDBHandler di file lain
# from influx_handler import InfluxDBHandler

class MQTTHandler:
    def __init__(self, influx_handler): # Hapus anotasi tipe jika InfluxDBHandler tidak diimpor
        self.influx_handler = influx_handler

        # 1. Inisialisasi Client dengan Websockets dan MQTTv5
        #    MQTTv5 memberikan pesan error yang lebih baik.
        self.client = mqtt.Client(
            client_id=config.MQTT_CLIENT_ID_LOGGER,
            protocol=mqtt.MQTTv5,
            transport="websockets"  # WAJIB untuk koneksi via Cloudflare
        )
        logging.info("MQTT Client diinisialisasi dengan transport WebSocket.")

        # 2. Atur Path untuk WebSocket
        #    Ini adalah langkah krusial. Path harus sesuai dengan konfigurasi broker (default EMQX: "/mqtt").
        self.client.ws_set_options(path=config.MQTT_WS_PATH)
        logging.info(f"WebSocket path diatur ke: {config.MQTT_WS_PATH}")

        # 3. Atur Enkripsi TLS (Wajib untuk WSS di port 443)
        #    Koneksi ke Cloudflare harus aman.
        self.client.tls_set(
            tls_version=ssl.PROTOCOL_TLS,
            cert_reqs=ssl.CERT_REQUIRED
        )
        logging.info("Enkripsi TLS untuk koneksi WSS telah diaktifkan.")

        # 4. Atur Kredensial (Username/Password)
        #    Diambil dari environment variables untuk keamanan.
        mqtt_user = os.getenv("MQTT_USER")
        mqtt_pass = os.getenv("MQTT_PASS")
        if mqtt_user and mqtt_pass:
            self.client.username_pw_set(mqtt_user, mqtt_pass)
            logging.info("Kredensial MQTT (username/password) telah diatur.")
        else:
            logging.warning("Username/password MQTT tidak ditemukan di environment. Mencoba koneksi anonim.")

        # 5. Atur Fungsi Callback
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback yang dipanggil saat berhasil atau gagal terhubung."""
        conn_str = mqtt.connack_string(rc)
        if rc == 0:
            logging.info(f"✅ Berhasil terhubung ke MQTT Broker! ({conn_str})")
            client.subscribe(config.MQTT_TOPIC_DATA)
            logging.info(f"📡 Berhasil subscribe ke topik: {config.MQTT_TOPIC_DATA}")
        else:
            logging.error(f"❌ Gagal terhubung ke MQTT. Kode: {rc}, Pesan: {conn_str}")
            if rc == 5:
                logging.error("   -> Detail: Autentikasi Gagal. Periksa kembali username dan password Anda.")
            elif "path" in str(conn_str).lower():
                logging.error("   -> Detail: Kemungkinan besar 'MQTT_WS_PATH' di config.py salah.")

    def _on_message(self, client, userdata, msg):
        """Callback yang dipanggil saat pesan baru diterima."""
        logging.info(f"📨 Pesan diterima dari topik: {msg.topic}")
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            logging.debug(f"📦 Payload JSON: {data}") # Gunakan DEBUG untuk log yang lebih detail

            # Validasi sederhana, bisa Anda kembangkan
            if 'gas_ppm' not in data or 'timestamp' not in data:
                logging.warning(f"⚠️ Pesan dilewati. Field 'gas_ppm' atau 'timestamp' tidak ada. Payload: {payload}")
                return

            # Kirim data ke InfluxDB
            self.influx_handler.write_data(data)
            logging.info("✅ Data berhasil dikirim ke InfluxDB.")

        except json.JSONDecodeError:
            logging.error(f"❌ Pesan bukan JSON valid. Payload: {msg.payload.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logging.error(f"⚠️ Terjadi error tak terduga di _on_message: {e}", exc_info=True)
            
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback yang dipanggil saat koneksi terputus."""
        if rc != 0:
            logging.warning(f"🔌 Koneksi MQTT terputus secara tak terduga dengan kode {rc}. Paho-MQTT akan mencoba menyambung kembali secara otomatis.")
        else:
            logging.info("🔌 Koneksi MQTT ditutup secara normal.")

    def start(self):
        """Memulai koneksi dan loop utama client."""
        try:
            logging.info(f"🚀 Mencoba menghubungkan ke broker {config.MQTT_BROKER}:{config.MQTT_PORT}...")
            self.client.connect(
                host=config.MQTT_BROKER,
                port=config.MQTT_PORT,
                keepalive=60
            )
            # loop_forever() adalah blocking call, akan menjalankan client sampai dihentikan.
            # Juga menangani proses reconnect secara otomatis.
            self.client.loop_forever()
        except socket.gaierror:
            logging.critical(f"🔥 Gagal Konek: Masalah DNS. Tidak dapat menemukan host '{config.MQTT_BROKER}'. Periksa nama domain dan koneksi internet Anda.")
        except ConnectionRefusedError:
            logging.critical(f"🔥 Gagal Konek: Connection refused. Pastikan Cloudflare Tunnel berjalan dan mengarah ke port EMQX yang benar (default: 8083).")
        except TimeoutError:
            logging.critical(f"🔥 Gagal Konek: Connection timed out. Periksa firewall atau masalah jaringan antara Anda dan Cloudflare.")
        except Exception as e:
            logging.critical(f"🔥 Terjadi error fatal saat memulai koneksi: {e}", exc_info=True)