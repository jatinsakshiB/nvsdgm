from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QLabel, QSpinBox,
    QComboBox, QMessageBox, QCheckBox, QWidget
)
from services.scanner_service import ScannerService
from database.sqlite_manager import SQLiteManager
from models.register import Register

class RegisterWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list)
    
    def __init__(self, scanner: ScannerService, client_params: dict, start: int, count: int, fc: int):
        super().__init__()
        self.scanner = scanner
        self.client_params = client_params
        self.start_addr = start
        self.count = count
        self.fc = fc

    def run(self):
        def progress_cb(current, total):
            self.progress.emit(current, total)
            
        results = self.scanner.discover_registers(
            self.client_params, self.start_addr, self.count, self.fc, progress_cb
        )
        self.finished.emit(results)

class RegisterDiscoveryDialog(QDialog):
    registers_added = Signal()
    
    def __init__(self, device_id: int, client_params: dict, db: SQLiteManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register Auto-Discovery")
        self.resize(600, 500)
        
        self.device_id = device_id
        self.client_params = client_params
        self.db = db
        self.scanner = ScannerService()
        self.found_registers = []
        
        layout = QVBoxLayout(self)
        
        # Settings
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Start Addr:"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 65535)
        settings_layout.addWidget(self.start_spin)
        
        settings_layout.addWidget(QLabel("Count:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1000)
        self.count_spin.setValue(100)
        settings_layout.addWidget(self.count_spin)
        
        settings_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Holding (FC 03)", 3)
        self.type_combo.addItem("Input (FC 04)", 4)
        settings_layout.addWidget(self.type_combo)
        
        self.scan_btn = QPushButton("Start Discovery")
        self.scan_btn.clicked.connect(self.start_discovery)
        settings_layout.addWidget(self.scan_btn)
        
        layout.addLayout(settings_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Address", "Live Value", "Add?"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Actions
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Selected Registers")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.add_selected)
        btn_layout.addWidget(self.add_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        self.worker = None

    def start_discovery(self):
        if self.worker and self.worker.isRunning():
            self.scanner.stop()
            return
            
        self.table.setRowCount(0)
        self.found_registers = []
        self.progress_bar.setValue(0)
        self.scan_btn.setText("Stop")
        
        start = self.start_spin.value()
        count = self.count_spin.value()
        fc = self.type_combo.currentData()
        
        self.worker = RegisterWorker(self.scanner, self.client_params, start, count, fc)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, current, total):
        val = int((current / total) * 100)
        self.progress_bar.setValue(val)

    def on_finished(self, results):
        self.found_registers = results
        self.scan_btn.setText("Start Discovery")
        self.update_table()
        self.add_btn.setEnabled(len(results) > 0)

    def update_table(self):
        self.table.setRowCount(0)
        for res in self.found_registers:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(res['address'])))
            self.table.setItem(row, 1, QTableWidgetItem(str(res['value'])))
            
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0,0,0,0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(True)
            chk_layout.addWidget(chk)
            self.table.setCellWidget(row, 2, chk_widget)

    def add_selected(self):
        added_count = 0
        for i in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(i, 2)
            chk = chk_widget.findChild(QCheckBox)
            if chk and chk.isChecked():
                res = self.found_registers[i]
                reg = Register(
                    name=f"Auto-{res['type']}-{res['address']}",
                    address=res['address'],
                    data_type="int16", # Default guess
                    function_code=3 if res['type'] == "Holding" else 4,
                    scaling_factor=1.0,
                    unit="",
                    device_id=self.device_id
                )
                self.db.add_register(reg)
                added_count += 1
                
        if added_count > 0:
            QMessageBox.information(self, "Success", f"Added {added_count} registers successfully.")
            self.registers_added.emit()
            self.close()
