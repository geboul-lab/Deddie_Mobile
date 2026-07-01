import os
import sys
import socket
import threading
import time
import random
from datetime import datetime

# Ρύθμιση μεγέθους παραθύρου για δοκιμή στο Desktop (προσομοίωση κινητού)
from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '640')

from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform

# Δομή του Mobile UI με Kivy Design Language (KV)
KV = '''
MDScreen:
    md_bg_color: 0.1, 0.1, 0.1, 1

    MDBoxLayout:
        orientation: 'vertical'
        padding: "16dp"
        spacing: "12dp"

        # Επάνω Μπάρα / Τίτλος
        MDLabel:
            text: "ΔΕΔΔΗΕ Mobile FUOTA"
            halign: "center"
            font_style: "H5"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            size_hint_y: None
            height: "40dp"

        # Πεδίο εισαγωγής ID Συσκευής
        MDTextField:
            id: target_id_input
            text: "000000000"
            hint_text: "Αριθμός Μετρητή"
            mode: "rectangle"
            multiline: False        # Κλειδώνει το πεδίο σε 1 γραμμή για να μην κουνιέται ο κέρσορας
            font_size: "16sp"       # Καθαρό και ευανάγνωστο μέγεθος
            size_hint_x: None       # Απενεργοποιούμε το ποσοστό πλάτους
            width: "120dp"          # Σταθερό, μαζεμένο πλάτος κατάλληλο για ID
            pos_hint: {"center_x": 0.5} # Κεντράρει το κουτί τέλεια στην οθόνη
            text_color_focus: 1, 1, 1, 1
            hint_text_color: 0.7, 0.7, 0.7, 1

        # Status Layout (Λαμπάκι & Κατάσταση)
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: "40dp"
            spacing: "10dp"
            
            MDIcon:
                id: status_led
                icon: "circle"
                theme_text_color: "Custom"
                text_color: 1, 0, 0, 1 # Κόκκινο αρχικά (Disconnected)
                size_hint_x: None
                width: "24dp"
            
            MDLabel:
                id: status_label
                text: "Waiting for UDP (Port 8081)..."
                theme_text_color: "Custom"
                text_color: 0.8, 0.8, 0.8, 1

        # Κουμπιά Διαχείρισης Αρχείου & Σύνδεσης
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: "8dp"
            size_hint_y: None
            height: "40dp"

            MDRaisedButton:
                text: "Create Bin"
                on_release: app.create_mock_bin()
            
            MDRaisedButton:
                text: "Disconnect"
                md_bg_color: 0.7, 0.1, 0.1, 1
                on_release: app.disconnect_tcp()

        # Κουμπιά FUOTA
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: "8dp"
            size_hint_y: None
            height: "40dp"

            MDRaisedButton:
                id: btn_fuota_rec
                text: "FUOTA Rec"
                disabled: True
                on_release: app.start_fuota(is_rx_only=True)
            
            MDRaisedButton:
                id: btn_fuota_trx
                text: "FUOTA Trx"
                disabled: True
                on_release: app.start_fuota(is_rx_only=False)

        # Δυναμικό κείμενο κατάστασης προόδου
        MDLabel:
            id: progress_status_text
            text: "Progress: 0%"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.8, 0.8, 0.8, 1
            size_hint_y: None
            height: "20dp"

        # Μπάρα Προόδου FUOTA
        MDProgressBar:
            id: fuota_progress
            value: 0
            max: 100
            size_hint_y: None
            height: "8dp"

        # Scrollable Log (Αντί για Memo)
        MDScrollView:
            do_scroll_x: False
            do_scroll_y: True
            bar_width: "4dp"
            
            MDLabel:
                id: log_output
                text: "System started...\\n"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 0, 1, 0, 1 # Πράσινα γράμματα
                size_hint_y: None
                height: self.texture_size[1]
                valign: "top"
'''

class MobileFuotaApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        
        # Αρχικοποίηση μεταβλητών κατάστασης
        self.tcp_client = None
        self.udp_server = None
        self.is_connected = False
        self.is_fuota_active = False
        self.is_fuota_rx_only = True
        self.file_size = 0
        self.file_crc32 = "00000000"
        self.chunk_size = 256
        self.fuota_last_action = datetime.now()
        
        # Καθορισμός φακέλου αποθήκευσης (Sandbox για κινητά)
        if platform == 'android':
            from android.storage import app_storage_path
            self.storage_path = app_storage_path()
        else:
            self.storage_path = os.path.dirname(os.path.abspath(__file__))
            
        self.bin_filename = os.path.join(self.storage_path, "testcode.bin")

        # Εκκίνηση του UDP Listener σε background thread
        threading.Thread(target=self.udp_listener_worker, daemon=True).start()
        
        # Timers για Keep Alive και Timeouts
        Clock.schedule_interval(self.keep_alive_tick, 10.0)
        Clock.schedule_interval(self.check_timeouts, 1.0)

        return Builder.load_string(KV)

    def log(self, message):
        """Ασφαλής προσθήκη μηνύματος στο Log UI από οποιοδήποτε thread"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_line = f"{timestamp} -> {message}\n"
        
        def update_label(dt):
            self.root.ids.log_output.text += full_line
        Clock.schedule_once(update_label)

    def create_mock_bin(self):
        """Δημιουργία τυχαίου binary αρχείου"""
        random_size = random.randint(25000, 30000)
        random_bytes = bytearray(random.getrandbits(8) for _ in range(random_size))
        
        import zlib
        crc = zlib.crc32(random_bytes) & 0xffffffff
        self.file_size = random_size
        self.file_crc32 = f"{crc:08X}"
        
        try:
            with open(self.bin_filename, "wb") as f:
                f.write(random_bytes)
            self.log(f"Created file: testcode.bin ({random_size} bytes, CRC: {self.file_crc32})")
        except Exception as e:
            self.log(f"File Creation Error: {str(e)}")

    def udp_listener_worker(self):
        """Background Thread: Ακούει στο UDP Port 8081"""
        self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.udp_server.bind(('0.0.0.0', 8081))
            self.log("UDP Server listening on port 8081...")
        except Exception as e:
            self.log(f"Failed to bind UDP port 8081: {str(e)}")
            return

        while True:
            try:
                data, addr = self.udp_server.recvfrom(1024)
                raw_str = data.decode('utf-8', errors='ignore')
                
                extracted_id = ""
                extracted_ip = ""
                
                if "ID:" in raw_str:
                    try:
                        extracted_id = raw_str.split("ID:")[1].split("-")[0].strip()
                    except: pass
                    
                if '"' in raw_str:
                    try:
                        extracted_ip = raw_str.split('"')[1]
                    except: pass

                target_id = self.root.ids.target_id_input.text
                
                if extracted_ip and extracted_id == target_id and not self.is_connected:
                    self.log(f"Device ID: {extracted_id} detected at {extracted_ip}")
                    threading.Thread(target=self.connect_tcp_worker, args=(extracted_ip, 8080), daemon=True).start()
            except Exception as e:
                time.sleep(1)

    def connect_tcp_worker(self, ip, port):
        """Background Thread: Πραγματοποιεί τη σύνδεση TCP"""
        try:
            self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_client.settimeout(5.0)
            self.tcp_client.connect((ip, port))
            self.tcp_client.settimeout(None)
            
            self.is_connected = True
            
            Clock.schedule_once(lambda dt: self.update_ui_connection_state(True, ip))
            self.log(f"Connected to TCP {ip}:{port}")
            
            self.tcp_reader_loop()
        except Exception as e:
            self.log(f"TCP Connection Failed: {str(e)}")
            self.disconnect_tcp()

    def update_ui_connection_state(self, connected, ip=""):
        """Ενημερώνει τα οπτικά στοιχεία της φόρμας για τη σύνδεση"""
        if connected:
            self.root.ids.status_led.text_color = (0, 1, 0, 1)
            self.root.ids.status_label.text = f"Connected to {ip}"
            self.root.ids.btn_fuota_rec.disabled = False
            self.root.ids.btn_fuota_trx.disabled = False
        else:
            self.root.ids.status_led.text_color = (1, 0, 0, 1)
            self.root.ids.status_label.text = "Waiting for UDP (Port 8081)..."
            self.root.ids.btn_fuota_rec.disabled = True
            self.root.ids.btn_fuota_trx.disabled = True
            self.root.ids.fuota_progress.value = 0
            self.root.ids.progress_status_text.text = "Progress: 0%" # <--- ΕΔΩ ΜΠΗΚΕ

    def disconnect_tcp(self):
        """Κλείνει με ασφάλεια το TCP Socket"""
        self.is_connected = False
        self.is_fuota_active = False
        if self.tcp_client:
            try:
                self.tcp_client.close()
            except: pass
        
        # Ενημέρωση του UI: Επαναφορά κατάστασης και μηδενισμός του Target ID σε "00"
        def reset_ui(dt):
            self.update_ui_connection_state(False)
            self.root.ids.target_id_input.text = "000000000" # <-- ΜΗΔΕΝΙΣΜΟΣ ΤΟΥ ID
            
        Clock.schedule_once(reset_ui)
        self.log("Disconnected from device.")

    def tcp_reader_loop(self):
        """Το κύριο Loop ανάγνωσης δεδομένων (Αντίστοιχο του Delphi Thread)"""
        while self.is_connected:
            try:
                ready_data = self.tcp_client.recv(1024)
                if not ready_data:
                    self.log("Connection closed by remote device.")
                    break
                
                incoming_msg = ""
                try:
                    incoming_msg = ready_data.decode('utf-8').strip()
                except:
                    pass

                # --- 1. ΕΛΕΓΧΟΣ ΓΙΑ ΕΝΤΟΛΕΣ FUOTA ---
                if incoming_msg:
                    # Έλεγχος για αιτήματα chunk
                    if ',' in incoming_msg:
                        command, value = incoming_msg.split(',', 1)
                        command = command.strip()
                        value = value.strip()
                        
                        if command in ['READY_FOR_CHUNK', 'ACK_CHUNK', 'RETRY_CHUNK']:
                            self.fuota_last_action = datetime.now()
                            self.is_fuota_active = True
                            chunk_idx = int(value)
                            threading.Thread(target=self.send_chunk, args=(chunk_idx,), daemon=True).start()
                            continue
                    
                    # Έλεγχος προόδου LoRa αναμετάδοσης (Transmitter)
                    if "LORA_PROG:" in incoming_msg:
                        self.fuota_last_action = datetime.now()
                        self.is_fuota_active = True
                        try:
                            prog_str = incoming_msg.split("LORA_PROG:")[1].replace("%", "").strip()
                            prog_val = int(prog_str)
                            
                            # Ενημέρωση της Progress Bar και του κειμένου σε TR: XX%
                            def update_tr_progress(dt):
                                self.root.ids.fuota_progress.value = prog_val
                                self.root.ids.progress_status_text.text = f"TR: {prog_val}%"
                            Clock.schedule_once(update_tr_progress)
                        except:
                            pass
                        continue

                    if "REMOTE_UPDATE_OK" in incoming_msg:
                        self.log("FUOTA: Remote Update completed successfully!")
                        self.is_fuota_active = False
                        
                        # Ορισμός της συνάρτησης (έχει 24 κενά)
                        def set_full_progress_rec(dt):
                            self.root.ids.fuota_progress.value = 100
                            self.root.ids.progress_status_text.text = "TR: 100%"
                            
                        # Εκτέλεση της συνάρτησης (έχει 24 κενά - ΑΚΡΙΒΩΣ κάτω από το def)
                        Clock.schedule_once(set_full_progress_rec)
                        continue


                    if "VERIFY SUCCESS" in incoming_msg:
                        self.log("Transfer to Receiver Completed Successfully!")
                        self.is_fuota_active = False
                         # Επαναφορά της μπάρας και του κειμένου προόδου
                        def reset_progress(dt):
                            self.root.ids.fuota_progress.value = 0
                            self.root.ids.progress_status_text.text = "Progress: 0%"
                        Clock.schedule_once(reset_progress)
                        continue                       

                    # ΝΕΟΣ ΕΛΕΓΧΟΣ: Διαχείριση ακύρωσης από τη συσκευή
                    if "DOWNLOAD ABORTED" in incoming_msg:
                        self.log("FUOTA: Finished by Receiver (LoRa Re-enabled).")
                        self.is_fuota_active = False
                        # <--- ΕΔΩ ΜΠΗΚΕ Ο ΜΗΔΕΝΙΣΜΟΣ
                        def reset_on_abort(dt):
                            self.root.ids.fuota_progress.value = 0
                            self.root.ids.progress_status_text.text = "Progress: 0%"
                        Clock.schedule_once(reset_on_abort)
                        continue
                
                # --- 2. ΕΛΕΓΧΟΣ ΓΙΑ OK & DATA (Μόνο αν ΔΕΝ είμαστε σε FUOTA) ---
                if not self.is_fuota_active:
                    if ready_data == b'OK\r\n' or ready_data == b'OK':
                        self.log("Heartbeat: OK")
                    else:
                        self.log(f"LoRa Data: Received {len(ready_data)} bytes")
                else:
                    if incoming_msg:
                        self.log(f"FUOTA Msg: {incoming_msg}")
                        
            except Exception as e:
                self.log(f"Reader Error: {str(e)}")
                break
                
        self.disconnect_tcp()

    def send_chunk(self, chunk_index):
        """Αποστολή του chunk firmware των 256 bytes στη συσκευή"""
        if not os.path.exists(self.bin_filename):
            self.log("Error: testcode.bin not found!")
            return
            
        try:
            with open(self.bin_filename, "rb") as f:
                f.seek(chunk_index * self.chunk_size)
                raw_chunk = f.read(self.chunk_size)
                
            file_bytes = os.path.getsize(self.bin_filename)
            total_chunks = file_bytes // self.chunk_size
            if file_bytes % self.chunk_size > 0:
                total_chunks += 1
                
            percent = int((chunk_index / total_chunks) * 100) if total_chunks > 0 else 0
            # Ενημέρωση της Progress Bar και του κειμένου σε REC: XX%
            def update_rec_progress(dt):
                self.root.ids.fuota_progress.value = percent
                self.root.ids.progress_status_text.text = f"REC: {percent}%"
            Clock.schedule_once(update_rec_progress)

            
            if raw_chunk:
                packet = bytearray()
                packet.append(0xAA)
                packet.append(0x55)
                packet.append((chunk_index >> 8) & 0xFF)
                packet.append(chunk_index & 0xFF)
                
                if len(raw_chunk) < self.chunk_size:
                    raw_chunk = raw_chunk + b'\xFF' * (self.chunk_size - len(raw_chunk))
                    
                packet.extend(raw_chunk)
                
                crc16 = self.calculate_crc16_ccitt(raw_chunk)
                packet.append((crc16 >> 8) & 0xFF)
                packet.append(crc16 & 0xFF)
                
                self.tcp_client.sendall(packet)
                self.log(f"Sent chunk {chunk_index}/{total_chunks}")
            else:
                # ΔΙΟΡΘΩΣΗ: Όταν τελειώσουν τα Chunks, ΔΕΝ κλείνουμε το self.is_fuota_active.
                # Περιμένουμε το τελικό VERIFY SUCCESS ή REMOTE_UPDATE_OK από τη συσκευή.
                finish_cmd = "FINISH_FUOTA_RX\n" if self.is_fuota_rx_only else "FINISH_FUOTA_TX\n"
                self.tcp_client.sendall(finish_cmd.encode('utf-8'))
                self.log("FUOTA: All packets sent. Waiting for final confirmation...")
                
        except Exception as e:
            self.log(f"Failed to send chunk: {str(e)}")
                    
    def calculate_crc16_ccitt(self, data):
        """Υπολογισμός CRC16 CCITT (Αντίστοιχο του CalculateCRC16_Delphi)"""
        crc = 0xFFFF
        for byte in data:
            crc = (crc >> 8) | (crc << 8) & 0xFFFF
            crc ^= byte
            crc ^= (crc & 0xFF) >> 4
            crc ^= (crc << 12) & 0xFFFF
            crc ^= ((crc & 0xFF) << 5) & 0xFFFF
        return crc
        
    def start_fuota(self, is_rx_only):
        """Έναρξη της διαδικασίας FUOTA"""
        if not self.is_connected or self.file_size == 0:
            self.log("Cannot start FUOTA. Ensure device is connected and bin file is created.")
            return
        self.is_fuota_active = True
        self.is_fuota_rx_only = is_rx_only
        self.fuota_last_action = datetime.now()
        cmd_type = "START_FUOTA_REC" if is_rx_only else "START_FUOTA_TRX"
        init_command = f"{cmd_type},{self.file_size},{self.file_crc32}\n"
        try:
            self.tcp_client.sendall(init_command.encode('utf-8'))
            self.log(f"FUOTA Started: Sent {init_command.strip()}")
        except Exception as e:
            self.log(f"Failed to start FUOTA: {str(e)}")
            self.is_fuota_active = False

    def keep_alive_tick(self, dt):
        """Timer Tick: Στέλνει PING αν είμαστε συνδεδεμένοι και όχι σε FUOTA"""
        if self.is_connected and not self.is_fuota_active:
            try:
                self.tcp_client.sendall(b"PING\n")
                self.root.ids.status_led.text_color = (1, 1, 0, 1)
                Clock.schedule_once(lambda d: setattr(self.root.ids.status_led, 'text_color', (0, 1, 0, 1)), 0.5)
            except:
                self.disconnect_tcp()
                
    def check_timeouts(self, dt):
        if self.is_fuota_active:
            if (datetime.now() - self.fuota_last_action).total_seconds() > 10:
                self.log("!!! FUOTA ABORTED: Timeout - Sent ABORT to Nucleo !!!")
                try:
                    self.tcp_client.sendall(b"ABORT_FUOTA\n")
                except: 
                    pass
                self.is_fuota_active = False
                
                # <--- ΕΔΩ ΜΠΗΚΕ Ο ΜΗΔΕΝΙΣΜΟΣ
                def reset_on_timeout(dt):
                    self.root.ids.fuota_progress.value = 0
                    self.root.ids.progress_status_text.text = "Progress: 0%"
                Clock.schedule_once(reset_on_timeout)


if __name__ == '__main__':
    MobileFuotaApp().run()


