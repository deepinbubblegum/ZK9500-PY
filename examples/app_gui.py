# File: app_gui.py
import sys
import io
import time
import logging

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QWidget, QInputDialog, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QFont

# Import our custom SDK
from zk9500 import ZK9500

# Suppress verbose USB logs to keep the console clean
logging.basicConfig(level=logging.WARNING)

# ==========================================
# Translation Dictionary for TH / EN
# ==========================================
# ==========================================
# Translation Dictionary for TH / EN
# ==========================================
TRANSLATIONS = {
    'th': {
        'window_title': 'ระบบสแกนลายนิ้วมือ ZK9500',
        'no_image': 'ไม่มีภาพ',
        'standby_init': 'เชื่อมต่อเครื่องสแกนแล้ว\nแสตนด์บาย: กรุณาวางนิ้วบนเครื่องสแกน',
        'standby': 'แสตนด์บาย: กรุณาวางนิ้วบนเครื่องสแกน',
        'btn_enroll': 'ลงทะเบียนพนักงานใหม่ (Enroll)',
        'btn_add': 'เพิ่มลายนิ้วมือ (Add)',
        'btn_delete': 'ลบลายนิ้วมือ (Delete)',
        'scanning': 'กำลังสแกนภาพ...',
        'verify_success': '✅ ยืนยันสำเร็จ! รหัสพนักงาน: {}\n(คะแนน: {})',
        'verify_fail': '❌ ไม่พบข้อมูลในระบบ\n(คะแนน: {})',
        'enroll_start': 'เริ่มลงทะเบียนรหัส {}\nกรุณาวางนิ้วครั้งที่ 1/{}',
        'enroll_next': '✅ สำเร็จ! กรุณายกนิ้วขึ้น\nและวางใหม่ครั้งที่ {}/{}',
        'enroll_done': '🎉 ลงทะเบียนรหัส {} สำเร็จ!',
        'add_start': 'เพิ่มลายนิ้วมือสำหรับรหัส {}\nกรุณาวางนิ้วครั้งที่ 1/{}',
        'add_done': '🎉 เพิ่มลายนิ้วมือสำเร็จ!',
        'dlg_title': 'ลงทะเบียน',
        'dlg_prompt': 'ป้อนรหัสพนักงาน (ตัวเลข):',
        'dlg_count_title': 'จำนวนครั้งการสแกน',
        'dlg_count_prompt': 'ต้องการสแกนเก็บนิ้วกี่ครั้ง? (แนะนำ 3-5 ครั้ง):',
        'dlg_user_id': 'รหัสพนักงาน',
        'dlg_select_user': 'เลือกรหัสพนักงาน:',
        'dlg_select_fp': 'เลือกลายนิ้วมือที่ต้องการลบ (ID):',
        'warn_title': 'ข้อผิดพลาด',
        'warn_msg': 'กรุณาป้อนรหัสพนักงานเป็นตัวเลขเท่านั้น',
        'warn_not_found': 'ไม่พบรหัสพนักงาน',
        'warn_no_fp': 'ไม่พบลายนิ้วมือสำหรับรหัสนี้',
        'lang_toggle': 'Switch to English',
        'delete_confirm': 'ยืนยันการลบ',
        'delete_confirm_msg': 'คุณต้องการลบลายนิ้วมือนี้หรือไม่?',
        'delete_success': '✅ ลบลายนิ้วมือสำเร็จ!',
    },
    'en': {
        'window_title': 'ZK9500 Fingerprint Scanner',
        'no_image': 'No Image',
        'standby_init': 'Scanner Connected\nStandby: Please place your finger',
        'standby': 'Standby: Please place your finger',
        'btn_enroll': 'Enroll New Employee',
        'btn_add': 'Add Fingerprint',
        'btn_delete': 'Delete Fingerprint',
        'scanning': 'Scanning image...',
        'verify_success': '✅ Verified! Employee ID: {}\n(Score: {})',
        'verify_fail': '❌ Not found in system\n(Score: {})',
        'enroll_start': 'Start enrollment for ID {}\nPlease place finger 1/{}',
        'enroll_next': '✅ Success! Please lift finger\nand place again {}/{}',
        'enroll_done': '🎉 Enrollment for ID {} successful!',
        'add_start': 'Add fingerprint for ID {}\nPlease place finger 1/{}',
        'add_done': '🎉 Added fingerprint successfully!',
        'dlg_title': 'Enrollment',
        'dlg_prompt': 'Enter Employee ID (Numbers only):',
        'dlg_count_title': 'Scan Count',
        'dlg_count_prompt': 'How many scans for enrollment? (Recommended: 3-5):',
        'dlg_user_id': 'Employee ID',
        'dlg_select_user': 'Select Employee ID:',
        'dlg_select_fp': 'Select fingerprint to delete (ID):',
        'warn_title': 'Error',
        'warn_msg': 'Please enter numeric Employee ID only.',
        'warn_not_found': 'Employee ID not found',
        'warn_no_fp': 'No fingerprints found for this ID',
        'lang_toggle': 'เปลี่ยนเป็นภาษาไทย',
        'delete_confirm': 'Confirm Delete',
        'delete_confirm_msg': 'Are you sure you want to delete this fingerprint?',
        'delete_success': '✅ Fingerprint deleted successfully!',
    }
}

# ==========================================
# 1. Hardware Thread for ZK9500 Scanner
# ==========================================
class ScannerThread(QThread):
    # Signals to communicate data back to the main GUI thread safely
    update_image_signal = pyqtSignal(bytes)       # Emits raw image bytes
    update_status_signal = pyqtSignal(str, str)   # Emits (Message text, Color)
    enroll_finished_signal = pyqtSignal()         # Emits when enrollment is complete

    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
        self.running = True
        self.mode = "VERIFY"
        self.enroll_id = None
        self.enroll_count = 3
        self.lang = 'th' # Default language for the thread

    def get_text(self, key):
        """Helper to get translated text based on current language"""
        return TRANSLATIONS[self.lang][key]

    def run(self):
        """Main background loop monitoring the scanner"""
        while self.running:
            if self.mode == "VERIFY":
                self._run_verify()
            elif self.mode == "ENROLL":
                self._run_enroll()
            elif self.mode == "ADD":
                self._run_add()
                
    def _run_verify(self):
        """Verification mode (Standby) logic"""
        if self.scanner.detect_finger():
            self.update_status_signal.emit(self.get_text('scanning'), "blue")
            capture_result = self.scanner.capture_image()
            
            if capture_result:
                raw_data, w, h = capture_result
                img = self.scanner.decode_from_bytes(raw_data)
                
                if img:
                    # Convert PIL image to byte array for GUI and DB processing
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()
                    
                    # 🌟 Emit image bytes to the GUI
                    self.update_image_signal.emit(img_bytes)
                    
                    # Verify against the database
                    is_match, matched_id, score = self.scanner.verify(img_bytes)
                    
                    if is_match:
                        msg = self.get_text('verify_success').format(matched_id, score)
                        self.update_status_signal.emit(msg, "green")
                    else:
                        msg = self.get_text('verify_fail').format(score)
                        self.update_status_signal.emit(msg, "red")
                        
            time.sleep(1.0) # Delay before accepting the next scan
            self.update_status_signal.emit(self.get_text('standby'), "black")
            
        else:
            time.sleep(0.1) # Prevent high CPU usage

    def _run_enroll(self):
        """Enrollment mode logic"""
        images_bytes = []
        msg_start = self.get_text('enroll_start').format(self.enroll_id, self.enroll_count)
        self.update_status_signal.emit(msg_start, "blue")
        
        for i in range(self.enroll_count):
            if not self.running: break
            
            captured = False
            while not captured and self.running:
                if self.scanner.detect_finger():
                    capture_result = self.scanner.capture_image()
                    if capture_result:
                        raw_data, w, h = capture_result
                        img = self.scanner.decode_from_bytes(raw_data)
                        if img:
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            img_bytes = img_byte_arr.getvalue()
                            
                            # Emit captured image to GUI
                            self.update_image_signal.emit(img_bytes)
                            images_bytes.append(img_bytes)
                            captured = True
                time.sleep(0.1)
                
            if i < (self.enroll_count - 1):
                msg_next = self.get_text('enroll_next').format(i + 2, self.enroll_count)
                self.update_status_signal.emit(msg_next, "orange")
                time.sleep(1)
                
        # Save to database if all scans are complete
        if len(images_bytes) == self.enroll_count:
            self.scanner.enroll(self.enroll_id, images_bytes)
            msg_done = self.get_text('enroll_done').format(self.enroll_id)
            self.update_status_signal.emit(msg_done, "green")
            time.sleep(1)
            
        # Reset state back to VERIFY
        self.mode = "VERIFY"
        self.enroll_finished_signal.emit()
        self.update_status_signal.emit(self.get_text('standby'), "black")

    def _run_add(self):
        """Add fingerprints mode logic"""
        images_bytes = []
        msg_start = self.get_text('add_start').format(self.enroll_id, self.enroll_count)
        self.update_status_signal.emit(msg_start, "blue")
        
        for i in range(self.enroll_count):
            if not self.running: break
            
            captured = False
            while not captured and self.running:
                if self.scanner.detect_finger():
                    capture_result = self.scanner.capture_image()
                    if capture_result:
                        raw_data, w, h = capture_result
                        img = self.scanner.decode_from_bytes(raw_data)
                        if img:
                            img_byte_arr = io.BytesIO()
                            img.save(img_byte_arr, format='PNG')
                            img_bytes = img_byte_arr.getvalue()
                            
                            self.update_image_signal.emit(img_bytes)
                            images_bytes.append(img_bytes)
                            captured = True
                time.sleep(0.1)
                
            if i < (self.enroll_count - 1):
                msg_next = self.get_text('enroll_next').format(i + 2, self.enroll_count)
                self.update_status_signal.emit(msg_next, "orange")
                time.sleep(1)
                
        # Add fingerprints to database if all scans are complete
        if len(images_bytes) == self.enroll_count:
            self.scanner.add_fingerprints(self.enroll_id, images_bytes)
            msg_done = self.get_text('add_done')
            self.update_status_signal.emit(msg_done, "green")
            time.sleep(1)
            
        # Reset state back to VERIFY
        self.mode = "VERIFY"
        self.enroll_finished_signal.emit()
        self.update_status_signal.emit(self.get_text('standby'), "black")

    def stop(self):
        """Safely stop the thread"""
        self.running = False
        self.wait()


# ==========================================
# 2. Main GUI Window
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
        self.lang = 'th' # Default language
        self.initUI()
        
        # Initialize and start the background hardware thread
        self.hw_thread = ScannerThread(self.scanner)
        self.hw_thread.lang = self.lang
        self.hw_thread.update_image_signal.connect(self.display_image)
        self.hw_thread.update_status_signal.connect(self.display_status)
        self.hw_thread.enroll_finished_signal.connect(self.on_enroll_finished)
        self.hw_thread.start()

    def get_text(self, key):
        """Helper to get translated text"""
        return TRANSLATIONS[self.lang][key]

    def initUI(self):
        """Setup user interface layout and styling"""
        self.setFixedSize(450, 750)
        self.setStyleSheet("background-color: #f0f0f0;")

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 0. Top bar for Language Toggle
        top_bar = QHBoxLayout()
        top_bar.addStretch() # Push button to the right
        self.lang_btn = QPushButton(self.get_text('lang_toggle'))
        self.lang_btn.setFixedSize(120, 30)
        self.lang_btn.setStyleSheet("background-color: #e0e0e0; border-radius: 5px; font-weight: bold;")
        self.lang_btn.clicked.connect(self.toggle_language)
        top_bar.addWidget(self.lang_btn)
        main_layout.addLayout(top_bar)

        # 1. Main Title
        self.title_label = QLabel(self.get_text('window_title'))
        self.title_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        # 2. Fingerprint Image Placeholder
        self.image_label = QLabel()
        self.image_label.setFixedSize(300, 375)
        self.image_label.setStyleSheet("background-color: white; border: 2px dashed #cccccc;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText(self.get_text('no_image'))
        main_layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # 3. Status Label
        self.status_label = QLabel(self.get_text('standby_init'))
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: black;")
        main_layout.addWidget(self.status_label)

        # 4. Enroll Button
        self.enroll_btn = QPushButton(self.get_text('btn_enroll'))
        self.enroll_btn.setMinimumHeight(50)
        self.enroll_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.enroll_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #005A9E; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.enroll_btn.clicked.connect(self.start_enrollment)
        main_layout.addWidget(self.enroll_btn)

        # 5. Add Fingerprints Button
        self.add_btn = QPushButton(self.get_text('btn_add'))
        self.add_btn.setMinimumHeight(50)
        self.add_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #107C10;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0B5A06; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.add_btn.clicked.connect(self.start_add_fingerprints)
        main_layout.addWidget(self.add_btn)

        # 6. Delete Fingerprints Button
        self.delete_btn = QPushButton(self.get_text('btn_delete'))
        self.delete_btn.setMinimumHeight(50)
        self.delete_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #D83B01;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #A32700; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.delete_btn.clicked.connect(self.delete_fingerprint)
        main_layout.addWidget(self.delete_btn)

        # Set central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        self.setWindowTitle(self.get_text('window_title'))

    def toggle_language(self):
        """Switch language between Thai and English"""
        self.lang = 'en' if self.lang == 'th' else 'th'
        self.hw_thread.lang = self.lang # Update thread language
        self.update_ui_texts()

    def update_ui_texts(self):
        """Refresh static texts on the GUI when language changes"""
        self.setWindowTitle(self.get_text('window_title'))
        self.title_label.setText(self.get_text('window_title'))
        self.lang_btn.setText(self.get_text('lang_toggle'))
        self.enroll_btn.setText(self.get_text('btn_enroll'))
        self.add_btn.setText(self.get_text('btn_add'))
        self.delete_btn.setText(self.get_text('btn_delete'))
        
        # Update image placeholder if no image is currently displayed
        if self.image_label.pixmap() is None:
            self.image_label.setText(self.get_text('no_image'))
            
        # Reset status text if currently in standby mode
        if self.hw_thread.mode == "VERIFY":
            self.status_label.setText(self.get_text('standby'))

    # --- Signal Handlers from Thread ---
    def display_image(self, image_bytes):
        """Update the fingerprint image on the screen"""
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        self.image_label.setPixmap(pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio))

    def display_status(self, text, color):
        """Update the status text and color"""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def start_enrollment(self):
        """Triggered when the Enroll button is clicked"""
        # 1. Show input dialog for Employee ID
        user_id_str, ok = QInputDialog.getText(self, self.get_text('dlg_title'), self.get_text('dlg_prompt'))
        
        if ok and user_id_str.isdigit():
            # 2. 🌟 Show input dialog for Scan Count (ค่าเริ่มต้นคือ 3, ต่ำสุด 1, สูงสุด 10)
            count, ok_count = QInputDialog.getInt(
                self, 
                self.get_text('dlg_count_title'), 
                self.get_text('dlg_count_prompt'), 
                3, 1, 10, 1
            )
            
            if ok_count:
                # Disable button to prevent multiple clicks
                self.enroll_btn.setEnabled(False)
                self.add_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                
                # 🌟 อัปเดตค่า enroll_count ให้กับ Thread
                self.hw_thread.enroll_id = int(user_id_str)
                self.hw_thread.enroll_count = count
                self.hw_thread.mode = "ENROLL"
                
        elif ok:
            # Show error if input is not a number
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_msg'))

    def start_add_fingerprints(self):
        """Triggered when the Add Fingerprints button is clicked"""
        # Get all users from database
        try:
            all_users = self.scanner.get_all_users()
        except:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_not_found'))
            return
        
        if not all_users:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_not_found'))
            return
        
        # Show dialog to select user
        user_list = [str(uid) for uid in all_users]
        user_id_str, ok = QInputDialog.getItem(
            self, 
            self.get_text('dlg_user_id'), 
            self.get_text('dlg_select_user'),
            user_list, 0, False
        )
        
        if ok and user_id_str:
            user_id = int(user_id_str)
            
            # Get scan count
            count, ok_count = QInputDialog.getInt(
                self, 
                self.get_text('dlg_count_title'), 
                self.get_text('dlg_count_prompt'), 
                1, 1, 5, 1
            )
            
            if ok_count:
                self.enroll_btn.setEnabled(False)
                self.add_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                
                self.hw_thread.enroll_id = user_id
                self.hw_thread.enroll_count = count
                self.hw_thread.mode = "ADD"

    def delete_fingerprint(self):
        """Triggered when the Delete Fingerprints button is clicked"""
        # Get all users from database
        try:
            all_users = self.scanner.get_all_users()
        except:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_not_found'))
            return
        
        if not all_users:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_not_found'))
            return
        
        # Show dialog to select user
        user_list = [str(uid) for uid in all_users]
        user_id_str, ok = QInputDialog.getItem(
            self, 
            self.get_text('dlg_user_id'), 
            self.get_text('dlg_select_user'),
            user_list, 0, False
        )
        
        if not ok or not user_id_str:
            return
        
        user_id = int(user_id_str)
        
        # Get fingerprints for this user
        try:
            fingerprints = self.scanner.list_user_fingerprints(user_id)
        except:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_no_fp'))
            return
        
        if not fingerprints:
            QMessageBox.warning(self, self.get_text('warn_title'), self.get_text('warn_no_fp'))
            return
        
        # Show dialog to select fingerprint to delete
        fp_list = [f"FP ID: {fp['id']}" for fp in fingerprints]
        fp_str, ok = QInputDialog.getItem(
            self, 
            self.get_text('dlg_select_fp'), 
            self.get_text('dlg_select_fp'),
            fp_list, 0, False
        )
        
        if ok and fp_str:
            fp_id = int(fp_str.split(": ")[1])
            
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                self.get_text('delete_confirm'),
                self.get_text('delete_confirm_msg'),
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    self.scanner.delete_fingerprint(fp_id)
                    QMessageBox.information(self, self.get_text('window_title'), self.get_text('delete_success'))
                except Exception as e:
                    QMessageBox.warning(self, self.get_text('warn_title'), str(e))

    def on_enroll_finished(self):
        """Re-enable the buttons once enrollment/add is complete"""
        self.enroll_btn.setEnabled(True)
        self.add_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def closeEvent(self, event):
        """Handle application close event (X button)"""
        print("Closing application...")
        self.hw_thread.stop()
        self.scanner.disconnect()
        event.accept()

# ==========================================
# Application Entry Point
# ==========================================
if __name__ == '__main__':
    # Initialize scanner before starting GUI
    scanner = ZK9500(db_name="fingerprints.sqlite")
    if not scanner.connect():
        print("❌ Error: ZK9500 Scanner not found. Please check the USB connection.")
        sys.exit(1)
        
    scanner.handshake()
    scanner.setup_normal_mode()

    # Start PyQt5 Application
    app = QApplication(sys.argv)
    window = MainWindow(scanner)
    window.show()
    sys.exit(app.exec_())