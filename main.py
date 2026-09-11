import sys
import os
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QComboBox, QSpinBox, QGroupBox,
    QFormLayout, QFrame, QHeaderView, QScrollArea
)
from PySide6.QtGui import QFont, QTextCursor, QIcon
from olt_manager import HuaweiOLT, validate_sn, validate_fsp

# ----------------- LOGGING CONFIGURATION -----------------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(BASE_DIR, "olt_manager.log")
logger = logging.getLogger("OLTManager")
logger.setLevel(logging.INFO)

if not logger.handlers:
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Log dosyası oluşturulamadı: {e}")

# ----------------- STYLESHEET -----------------
QSS_STYLE = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    color: #E2E8F0;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
QGroupBox {
    border: 1px solid #2D3748;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    font-size: 13px;
    color: #00ADB5;
    background-color: #1E1E24;
    padding: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #121214;
    border: 1px solid #4A5568;
    border-radius: 5px;
    padding: 5px 10px;
    color: #E2E8F0;
    min-height: 22px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #00ADB5;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #1A1A1E;
    color: #718096;
    border: 1px solid #2D3748;
}
QPushButton {
    background-color: #00ADB5;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    color: #121214;
    font-weight: bold;
    font-size: 13px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #00FFF5;
}
QPushButton:pressed {
    background-color: #008F95;
}
QPushButton:disabled {
    background-color: #2D3748;
    color: #718096;
}
QTableWidget {
    background-color: #1E1E24;
    border: 1px solid #2D3748;
    gridline-color: #2D3748;
    border-radius: 6px;
    alternate-background-color: #15151A;
}
QTableWidget::item {
    padding: 5px;
}
QTableWidget::item:selected {
    background-color: #00ADB5;
    color: #121214;
    font-weight: bold;
}
QHeaderView::section {
    background-color: #121214;
    color: #A0AEC0;
    padding: 6px;
    border: 1px solid #2D3748;
    font-weight: bold;
}
QScrollBar:vertical {
    border: none;
    background: #121214;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #4A5568;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00ADB5;
}
QScrollBar:horizontal {
    border: none;
    background: #121214;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #4A5568;
    min-width: 20px;
    border-radius: 4px;
}
QTextEdit {
    background-color: #0F0F11;
    border: 1px solid #2D3748;
    border-radius: 6px;
    color: #C5C6C7;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}
QMessageBox {
    background-color: #1E1E24;
    color: #E2E8F0;
}
QMessageBox QLabel {
    color: #E2E8F0;
    font-size: 13px;
}
QMessageBox QPushButton {
    background-color: #00ADB5;
    color: #121214;
    font-weight: bold;
    padding: 6px 16px;
    border-radius: 4px;
}
QMessageBox QPushButton:hover {
    background-color: #00FFF5;
}
"""

class OLTWorker(QThread):
    """
    OLT işlemlerinin arayüzü dondurmaması için arka planda çalışan thread sınıfı.
    """
    finished = Signal(bool, str, object)  # success, message, result_data
    
    def __init__(self, action, olt_instance, *args, **kwargs):
        super().__init__()
        self.action = action
        self.olt = olt_instance
        self.args = args
        self.kwargs = kwargs
        
    def run(self):
        try:
            if self.action == "connect":
                prompt = self.olt.connect()
                self.finished.emit(True, f"OLT Bağlantısı Başarılı: {prompt}", None)
            elif self.action == "find_onts":
                onts = self.olt.find_onts()
                self.finished.emit(True, f"{len(onts)} yeni ONT bulundu.", onts)
            elif self.action == "register":
                result = self.olt.register_ont(*self.args, **self.kwargs)
                self.finished.emit(True, "ONT Kaydı Tamamlandı.", result)
            elif self.action == "delete_ont":
                result = self.olt.delete_ont_by_sn(*self.args, **self.kwargs)
                self.finished.emit(True, "Modem silme tamamlandı.", result)
        except Exception as e:
            self.finished.emit(False, str(e), None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPON OLT Manager - Huawei MA5680T")
        self.resize(1200, 760)
        self.setMinimumSize(960, 600)
        self.olt = None
        self.worker = None

        # Stil şablonunu uygula
        self.setStyleSheet(QSS_STYLE)

        # Ana widget ve layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # ---------------- LEFT SIDEBAR (SCROLLABLE AREA) ----------------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setMinimumWidth(320)
        left_scroll.setMaximumWidth(400)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 8, 5)
        left_layout.setSpacing(10)
        
        # Logo / Title
        brand_label = QLabel("GPON OLT MANAGER")
        brand_label.setAlignment(Qt.AlignCenter)
        brand_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ADB5; padding: 5px 0px 0px 0px;")
        left_layout.addWidget(brand_label)

        credit_sub = QLabel("by M. Furkan Erkan")
        credit_sub.setAlignment(Qt.AlignCenter)
        credit_sub.setStyleSheet("font-size: 11px; color: #718096; font-weight: bold; margin-bottom: 5px;")
        left_layout.addWidget(credit_sub)

        # 1. OLT Bağlantı Kutusu
        conn_group = QGroupBox("OLT BAĞLANTI AYARLARI")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(8)
        conn_form.setContentsMargins(8, 12, 8, 8)

        self.host = QLineEdit()
        self.host.setText("mock")
        self.host.setPlaceholderText("Örn: mock veya 192.168.1.1")
        
        self.user = QLineEdit()
        self.user.setText("admin")
        self.user.setPlaceholderText("Kullanıcı adı")
        
        self.password = QLineEdit()
        self.password.setText("admin")
        self.password.setPlaceholderText("Şifre")
        self.password.setEchoMode(QLineEdit.Password)

        self.protocol = QComboBox()
        self.protocol.addItems(["SSH", "Telnet"])
        self.protocol.currentIndexChanged.connect(self.on_protocol_changed)

        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(22)

        self.connect_btn = QPushButton("OLT'YE BAĞLAN")
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        conn_form.addRow("OLT IP Adresi:", self.host)
        conn_form.addRow("Protokol:", self.protocol)
        conn_form.addRow("Port:", self.port)
        conn_form.addRow("Kullanıcı:", self.user)
        conn_form.addRow("Şifre:", self.password)
        conn_form.addRow("", self.connect_btn)
        
        left_layout.addWidget(conn_group)

        # 2. Kayıt Parametreleri Kutusu
        param_group = QGroupBox("ONT KAYIT PARAMETRELERİ")
        param_form = QFormLayout(param_group)
        param_form.setSpacing(8)
        param_form.setContentsMargins(8, 12, 8, 8)

        self.vlan = QSpinBox()
        self.vlan.setRange(1, 4094)
        self.vlan.setValue(2024)

        self.profile = QSpinBox()
        self.profile.setRange(1, 4096)
        self.profile.setValue(10)

        self.srvprofile = QSpinBox()
        self.srvprofile.setRange(1, 4096)
        self.srvprofile.setValue(1)

        self.gemport = QSpinBox()
        self.gemport.setRange(1, 128)
        self.gemport.setValue(1)

        self.user_vlan = QSpinBox()
        self.user_vlan.setRange(1, 4094)
        self.user_vlan.setValue(1)

        param_form.addRow("VLAN ID:", self.vlan)
        param_form.addRow("Line Profile ID:", self.profile)
        param_form.addRow("Service Profile ID:", self.srvprofile)
        param_form.addRow("Gemport ID:", self.gemport)
        param_form.addRow("User VLAN:", self.user_vlan)

        left_layout.addWidget(param_group)

        # 3. Kayıt Silme Kutusu
        delete_group = QGroupBox("ONT KAYIT SİLME")
        delete_form = QFormLayout(delete_group)
        delete_form.setSpacing(8)
        delete_form.setContentsMargins(8, 12, 8, 8)

        self.delete_sn = QLineEdit()
        self.delete_sn.setPlaceholderText("Silinecek SN (Örn: 48575443...)")

        self.delete_btn = QPushButton("KAYDI SİL")
        self.delete_btn.setStyleSheet("background-color: #EF4444; color: white;")
        self.delete_btn.clicked.connect(self.delete_ont_confirm)
        self.delete_btn.setEnabled(False)

        delete_form.addRow("Seri No (SN):", self.delete_sn)
        delete_form.addRow("", self.delete_btn)

        left_layout.addWidget(delete_group)
        left_layout.addStretch()

        left_scroll.setWidget(left_panel)

        # ---------------- RIGHT CONTENT AREA ----------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Üst Butonlar
        actions_layout = QHBoxLayout()
        self.find_btn = QPushButton("YENİ ONT'LERİ BUL")
        self.find_btn.setEnabled(False)
        self.find_btn.clicked.connect(self.find_onts)

        self.auto_btn = QPushButton("SEÇİLİ ONT'Yİ KAYDET")
        self.auto_btn.setEnabled(False)
        self.auto_btn.clicked.connect(self.register_selected)
        
        self.open_log_btn = QPushButton("📄 Log Dosyasını Aç")
        self.open_log_btn.setStyleSheet("background-color: #2D3748; color: #E2E8F0;")
        self.open_log_btn.clicked.connect(self.open_log_file)

        self.clear_btn = QPushButton("Logları Temizle")
        self.clear_btn.setStyleSheet("background-color: #2D3748; color: #E2E8F0;")
        self.clear_btn.clicked.connect(self.clear_logs)

        actions_layout.addWidget(self.find_btn)
        actions_layout.addWidget(self.auto_btn)
        actions_layout.addStretch()
        actions_layout.addWidget(self.open_log_btn)
        actions_layout.addWidget(self.clear_btn)
        right_layout.addLayout(actions_layout)

        # Tablo
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "OLT No", "F/S/P (Liman)", "Seri Numarası (SN)", "Model (Cihaz)", "Yazılım Sürümü", "Tespit Zamanı"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        
        # Tablo genişlik oranları
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        
        right_layout.addWidget(self.table, stretch=3)
        self.table.itemSelectionChanged.connect(self.on_ont_selected)

        # Log Çıktısı Kutusu
        log_group = QGroupBox("TERMİNAL VE İŞLEM KAYITLARI")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 12, 8, 8)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("İşlem adımları burada görüntülenecektir...")
        log_layout.addWidget(self.log)
        
        right_layout.addWidget(log_group, stretch=2)

        # Layoutları birleştir
        main_layout.addWidget(left_scroll, stretch=1)
        main_layout.addWidget(right_panel, stretch=3)

        self.statusBar().showMessage("OLT bağlantısı bekleniyor. Simülasyon modu için IP alanına 'mock' yazabilirsiniz.")
        
        # Sağ alt status bar geliştirici imzası
        credit_status = QLabel("by M. Furkan Erkan  ")
        credit_status.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 11px; padding-right: 8px;")
        self.statusBar().addPermanentWidget(credit_status)

        self.log_msg("Uygulama hazır. Bağlantı kurulması bekleniyor.", "info")

    def open_log_file(self):
        """Log dosyasını varsayılan metin editörü (Notepad vb.) ile açar."""
        if not os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(f"--- GPON OLT Manager Log Dosyası Başlatıldı ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Log dosyası oluşturulamadı: {e}")
                return
        try:
            if sys.platform == "win32":
                os.startfile(LOG_FILE)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", LOG_FILE])
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Log dosyası açılamadı: {e}")

    def log_msg(self, text, log_type="info"):
        """
        Renkli HTML formatında arayüze ekler ve aynı zamanda 'olt_manager.log' dosyasına yazar.
        """
        color_map = {
            "info": "#A0AEC0",
            "success": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "cmd": "#00ADB5"
        }
        color = color_map.get(log_type, "#E2E8F0")
        
        prefix_map = {
            "info": "[BİLGİ] ",
            "success": "[OK] ",
            "warning": "[UYARI] ",
            "error": "[HATA] ",
            "cmd": "[KOMUT] "
        }
        prefix = prefix_map.get(log_type, "")

        # Arayüz için HTML formatı
        if log_type == "cmd":
            html_msg = f'<span style="color: {color}; font-family: monospace;"><b>{text}</b></span>'
        else:
            html_msg = f'<span style="color: {color};">{prefix}{text}</span>'
            
        self.log.append(html_msg)
        self.log.moveCursor(QTextCursor.End)

        # Dosyaya loglama
        plain_text = re.sub(r'<[^>]+>', '', text)
        full_msg = f"{prefix}{plain_text}"
        if log_type == "error":
            logger.error(full_msg)
        elif log_type == "warning":
            logger.warning(full_msg)
        else:
            logger.info(full_msg)

    def clear_logs(self):
        self.log.clear()
        self.log_msg("Log ekranı temizlendi.", "info")

    def on_protocol_changed(self, index):
        """
        SSH seçilince portu 22, Telnet seçilince 23 yapar ve güvenlik uyarısı verir.
        """
        protocol = self.protocol.currentText()
        if protocol == "SSH":
            self.port.setValue(22)
        elif protocol == "Telnet":
            self.port.setValue(23)
            QMessageBox.warning(
                self,
                "Güvenlik Uyarısı (Telnet)",
                "⚠️ DİKKAT: Telnet protokolü şifrelenmemiş (düz metin) veri iletimi yapar.\n\n"
                "Kullanıcı adı, şifre ve OLT konfigürasyon komutları yerel ağda dinlenebilir (sniffing).\n\n"
                "Güvenliğiniz için SSH protokolünü kullanmanız önemle tavsiye edilir."
            )

    def toggle_connection(self):
        """
        Bağlantı kurar veya keser.
        """
        if self.olt:
            # Bağlantıyı kes
            self.olt.disconnect()
            self.olt = None
            self.connect_btn.setText("OLT'YE BAĞLAN")
            self.connect_btn.setStyleSheet("")
            self.find_btn.setEnabled(False)
            self.auto_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.host.setEnabled(True)
            self.user.setEnabled(True)
            self.password.setEnabled(True)
            self.protocol.setEnabled(True)
            self.port.setEnabled(True)
            self.statusBar().showMessage("Bağlantı kesildi.")
            self.log_msg("Bağlantı kesildi.", "warning")
            self.table.setRowCount(0)
            return

        # Bağlantı bilgilerini al
        host = self.host.text().strip()
        user = self.user.text().strip()
        password = self.password.text()
        protocol = self.protocol.currentText().lower()
        port = self.port.value()
        
        if host.lower() != "mock" and (not host or not user or not password):
            QMessageBox.warning(self, "Hata", "Lütfen tüm bağlantı bilgilerini doldurun.")
            return
            
        self.log_msg(f"OLT bağlantısı kuruluyor ({host}:{port} - {protocol.upper()})...", "info")
        self.connect_btn.setEnabled(False)
        self.statusBar().showMessage("Bağlanıyor...")
        
        try:
            olt = HuaweiOLT(host, user, password, port, protocol)
        except Exception as e:
            self.connect_btn.setEnabled(True)
            self.statusBar().showMessage("Bağlantı parametre hatası")
            self.log_msg(f"Hata: {e}", "error")
            QMessageBox.critical(self, "Parametre Hatası", str(e))
            return
        
        self.worker = OLTWorker("connect", olt)
        self.worker.finished.connect(lambda success, msg, data: self.on_connect_finished(success, msg, olt))
        self.worker.start()

    def on_connect_finished(self, success, msg, olt_instance):
        self.connect_btn.setEnabled(True)
        if success:
            self.olt = olt_instance
            self.connect_btn.setText("BAĞLANTIYI KES")
            self.connect_btn.setStyleSheet("background-color: #EF4444; color: white;")
            self.find_btn.setEnabled(True)
            self.auto_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.host.setEnabled(False)
            self.user.setEnabled(False)
            self.password.setEnabled(False)
            self.protocol.setEnabled(False)
            self.port.setEnabled(False)
            self.statusBar().showMessage("Bağlandı")
            self.log_msg(msg, "success")
            
            # Bağlandıktan sonra otomatik olarak modemleri sorgula
            self.find_onts()
        else:
            self.statusBar().showMessage("Bağlantı başarısız")
            self.log_msg(f"Bağlantı hatası: {msg}", "error")
            QMessageBox.critical(self, "Bağlantı Hatası", msg)

    def find_onts(self):
        """
        Kayıt bekleyen ONT'leri sorgular.
        """
        if not self.olt:
            return
            
        self.log_msg("Kayıt bekleyen ONT'ler sorgulanıyor (display ont autofind all)...", "info")
        self.find_btn.setEnabled(False)
        self.statusBar().showMessage("Sorgulanıyor...")
        
        self.worker = OLTWorker("find_onts", self.olt)
        self.worker.finished.connect(self.on_find_onts_finished)
        self.worker.start()

    def on_find_onts_finished(self, success, msg, data):
        self.find_btn.setEnabled(True)
        if success:
            self.statusBar().showMessage("Sorgulama tamamlandı")
            self.log_msg(msg, "success")
            
            self.table.setRowCount(0)
            if not data:
                self.log_msg("Kayıt bekleyen modem bulunamadı.", "warning")
                return
                
            for ont in data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                items = [
                    QTableWidgetItem(ont.get("number", "-")),
                    QTableWidgetItem(ont.get("fsp", "-")),
                    QTableWidgetItem(ont.get("sn", "-")),
                    QTableWidgetItem(ont.get("equipment_id", "-")),
                    QTableWidgetItem(ont.get("version", "-")),
                    QTableWidgetItem(ont.get("time", "-")),
                ]
                for col, item in enumerate(items):
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    self.table.setItem(row, col, item)
        else:
            self.statusBar().showMessage("Sorgulama başarısız")
            self.log_msg(f"Sorgulama hatası: {msg}", "error")
            QMessageBox.critical(self, "Hata", msg)

    def register_selected(self):
        """
        Seçilen ONT'yi kayıt parametreleriyle kaydeder.
        """
        if not self.olt:
            return
            
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Seçim Hatası", "Lütfen tablodan kaydetmek istediğiniz ONT'yi seçin.")
            return
            
        fsp = self.table.item(row, 1).text()
        sn = self.table.item(row, 2).text()
        
        try:
            validate_fsp(fsp)
            validate_sn(sn)
        except ValueError as e:
            QMessageBox.warning(self, "Doğrulama Hatası", str(e))
            return
            
        vlan = self.vlan.value()
        line_profile = self.profile.value()
        srv_profile = self.srvprofile.value()
        gemport = self.gemport.value()
        user_vlan = self.user_vlan.value()
        
        self.log_msg(f"ONT kaydı başlatıldı. SN: {sn}, F/S/P: {fsp}", "info")
        self.auto_btn.setEnabled(False)
        self.statusBar().showMessage("ONT kaydediliyor...")
        
        self.worker = OLTWorker(
            "register", self.olt,
            fsp, sn, line_profile, srv_profile, vlan, gemport, user_vlan
        )
        self.worker.finished.connect(self.on_register_finished)
        self.worker.start()

    def on_register_finished(self, success, msg, data):
        self.auto_btn.setEnabled(True)
        if success:
            self.statusBar().showMessage("Kayıt başarılı")
            self.log_msg("✓ Kayıt İşlemi Başarıyla Tamamlandı!", "success")
            
            if data:
                self.log_msg("--- OLT İşlem Detayları ---", "info")
                for line in data.splitlines():
                    if line.startswith(">"):
                        self.log_msg(line, "cmd")
                    elif "successfully" in line.lower() or "success" in line.lower() or "✓" in line:
                        self.log_msg(line, "success")
                    elif "error" in line.lower() or "failure" in line.lower() or "fail" in line.lower():
                        self.log_msg(line, "error")
                    else:
                        self.log_msg(line, "info")
                self.log_msg("---------------------------", "info")
            
            # Kayıt sonrası tabloyu yenile
            self.find_onts()
        else:
            self.statusBar().showMessage("Kayıt başarısız")
            self.log_msg(f"Kayıt Hatası: {msg}", "error")
            QMessageBox.critical(self, "Kayıt Hatası", msg)

    def on_ont_selected(self):
        """
        Tablodan bir ONT seçildiğinde tetiklenir.
        VLAN ID = 2000 + (Slot * 24) + Port formülüne göre yerel hesaplama yapar.
        """
        row = self.table.currentRow()
        if row < 0:
            return
            
        fsp_item = self.table.item(row, 1)
        if not fsp_item:
            return
        fsp = fsp_item.text()
        
        try:
            frame, slot, port = validate_fsp(fsp)
            vlan_id = 2000 + (slot * 24) + port
            if 1 <= vlan_id <= 4094:
                self.vlan.setValue(vlan_id)
                self.statusBar().showMessage(f"VLAN otomatik ayarlandı: {vlan_id}")
                self.log_msg(f"✓ Port konumuna göre VLAN ID otomatik hesaplandı: {vlan_id} (F/S/P: {fsp})", "success")
        except ValueError:
            pass

    def delete_ont_confirm(self):
        """
        Modem silme öncesi format doğrulaması ve onay penceresi gösterir.
        """
        sn = self.delete_sn.text().strip()
        if not sn:
            QMessageBox.warning(self, "Hata", "Lütfen silmek istediğiniz modemin seri numarasını (SN) girin.")
            return

        try:
            sn = validate_sn(sn)
        except ValueError as e:
            QMessageBox.warning(self, "Geçersiz Seri Numarası", str(e))
            return

        reply = QMessageBox.question(
            self, 'Modem Silme Onayı',
            f"⚠️ DİKKAT: '{sn}' seri numaralı modemin OLT üzerindeki TÜM kayıtları ve servis portları silinecektir.\n\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.delete_ont_action(sn)

    def delete_ont_action(self, sn):
        """
        Modem silme işlemini arka planda başlatır.
        """
        if not self.olt:
            return

        self.log_msg(f"Modem silme işlemi başlatılıyor. SN: {sn}", "info")
        self.delete_btn.setEnabled(False)
        self.statusBar().showMessage("Modem siliniyor...")

        self.worker = OLTWorker("delete_ont", self.olt, sn)
        self.worker.finished.connect(self.on_delete_finished)
        self.worker.start()

    def on_delete_finished(self, success, msg, data):
        self.delete_btn.setEnabled(True)
        self.delete_sn.clear()
        
        if success:
            self.statusBar().showMessage("Modem başarıyla silindi")
            self.log_msg("✓ Silme İşlemi Başarıyla Tamamlandı!", "success")
            
            if data:
                self.log_msg("--- OLT Silme İşlem Detayları ---", "info")
                for line in data.splitlines():
                    if line.startswith(">"):
                        self.log_msg(line, "cmd")
                    elif "successfully" in line.lower() or "success" in line.lower() or "✓" in line:
                        self.log_msg(line, "success")
                    elif "error" in line.lower() or "failure" in line.lower() or "fail" in line.lower():
                        self.log_msg(line, "error")
                    else:
                        self.log_msg(line, "info")
                self.log_msg("---------------------------------", "info")
                
            # Tabloyu yenile
            self.find_onts()
        else:
            self.statusBar().showMessage("Silme işlemi başarısız")
            self.log_msg(f"Silme Hatası: {msg}", "error")
            QMessageBox.critical(self, "Silme Hatası", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())
