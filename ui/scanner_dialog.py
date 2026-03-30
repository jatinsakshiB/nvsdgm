from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QLabel, QLineEdit,
    QMessageBox, QTextEdit, QWidget
)
from services.scanner_service import ScannerService, ScanResult
import asyncio

class ScanWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list)
    
    def __init__(self, subnet: str, scanner: ScannerService):
        super().__init__()
        self.subnet = subnet
        self.scanner = scanner

    def run(self):
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def progress_cb(current, total):
            self.progress.emit(current, total)
            
        try:
            results = loop.run_until_complete(self.scanner.scan_subnet(self.subnet, progress_cb))
            self.finished.emit(results)
        except Exception as e:
            print(f"Scanner Worker Error: {e}")
            self.finished.emit([])
        finally:
            loop.close()

class ScannerDialog(QDialog):
    add_device_requested = Signal(str, int)  # ip, port
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modbus Network Discovery")
        self.resize(900, 650)
        
        self.scanner = ScannerService()
        self.all_results = []
        
        layout = QVBoxLayout(self)
        
        # Header / Subnet
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Network Scanner</b>"))
        header_layout.addStretch()
        
        subnet_box = QHBoxLayout()
        subnet_box.addWidget(QLabel("Subnet:"))
        self.subnet_input = QLineEdit()
        local_ip = self.scanner.get_local_ip()
        self.subnet_input.setText(self.scanner.get_subnet(local_ip))
        self.subnet_input.setPlaceholderText("e.g. 192.168.1")
        subnet_box.addWidget(self.subnet_input)
        
        self.scan_btn = QPushButton("Start Discovery")
        self.scan_btn.setMinimumWidth(120)
        self.scan_btn.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.scan_btn.clicked.connect(self.start_scan)
        subnet_box.addWidget(self.scan_btn)
        
        self.export_btn = QPushButton("Export JSON")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_json)
        subnet_box.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)
        layout.addLayout(subnet_box)
        
        # Progress
        self.progress_layout = QVBoxLayout()
        self.progress_label = QLabel("Scanner ready.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 254)
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        layout.addLayout(self.progress_layout)
        
        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["IP Address", "Status", "Modbus Valid", "Latency (ms)", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        # Log viewer
        layout.addWidget(QLabel("<b>Diagnostic Logs (select a device above):</b>"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #f8f9fa; font-family: monospace;")
        self.log_display.setMaximumHeight(200)
        layout.addWidget(self.log_display)
        
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        self.worker = None

    def start_scan(self):
        if self.worker and self.worker.isRunning():
            self.scanner.stop()
            self.scan_btn.setText("Stopping...")
            self.scan_btn.setEnabled(False)
            return

        subnet = self.subnet_input.text().strip()
        if not subnet or subnet.count('.') < 2:
            QMessageBox.warning(self, "Invalid Subnet", "Please enter a valid subnet prefix (e.g., 192.168.1).")
            return

        self.table.setRowCount(0)
        self.all_results = []
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Scanning subnet {subnet}.1-254...")
        self.scan_btn.setText("Stop Discovery")
        self.scan_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self.log_display.clear()
        
        self.worker = ScanWorker(subnet, self.scanner)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Scanning... {current}/{total} checked")

    def on_finished(self, results):
        self.all_results = results
        self.scan_btn.setText("Start Discovery")
        self.scan_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.scan_btn.setStyleSheet("background-color: #2c3e50; color: white;")
        self.progress_label.setText(f"Scan complete. Found {len([r for r in results if r.is_online])} reachable addresses.")
        self.update_table()

    def update_table(self):
        self.table.setRowCount(0)
        # Filter for only reachable devices
        reachable = [r for r in self.all_results if r.is_online or r.port_open]
        # Sort Modbus devices to top
        sorted_results = sorted(reachable, key=lambda x: (not x.is_modbus, not x.port_open, x.ip))
        
        for res in sorted_results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            ip_item = QTableWidgetItem(res.ip)
            ip_item.setData(Qt.UserRole, res) # Store result object
            self.table.setItem(row, 0, ip_item)
            
            status_item = QTableWidgetItem(res.status_msg)
            if res.is_modbus:
                status_item.setForeground(Qt.darkGreen)
            elif res.port_open:
                status_item.setForeground(Qt.blue)
            self.table.setItem(row, 1, status_item)
            
            modbus_item = QTableWidgetItem("✅ YES" if res.is_modbus else "⚠️ NO")
            modbus_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, modbus_item)
            
            latency = f"{res.response_time:.1f}" if res.response_time > 0 else "-"
            self.table.setItem(row, 3, QTableWidgetItem(latency))
            
            add_btn = QPushButton("Use Device")
            add_btn.clicked.connect(lambda checked=False, r=res: self.emit_add(r))
            self.table.setCellWidget(row, 4, add_btn)

    def on_selection_changed(self):
        sel = self.table.selectedItems()
        if not sel:
            self.log_display.clear()
            return
        
        row = sel[0].row()
        ip_item = self.table.item(row, 0)
        res = ip_item.data(Qt.UserRole)
        if res:
            self.log_display.setText("\n".join(res.logs))

    def emit_add(self, res: ScanResult):
        self.add_device_requested.emit(res.ip, 502)

    def export_json(self):
        import json, os
        from PySide6.QtWidgets import QFileDialog
        
        path, _ = QFileDialog.getSaveFileName(self, "Export Results", os.getcwd(), "JSON Files (*.json)")
        if not path:
            return
            
        data = []
        for r in self.all_results:
            data.append({
                "ip": r.ip,
                "is_online": r.is_online,
                "port_open": r.port_open,
                "is_modbus": r.is_modbus,
                "response_time": r.response_time,
                "status": r.status_msg,
                "logs": r.logs
            })
            
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Export", f"Results exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")
        # Optional: highlight that it was sent to manager
        # QMessageBox.information(self, "Scanner", f"Configuration for {res.ip} passed to manager.")
