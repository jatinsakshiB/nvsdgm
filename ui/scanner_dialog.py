from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QProgressBar, QLabel, QLineEdit,
    QMessageBox, QTextEdit, QWidget, QTabWidget, QComboBox
)
from services.scanner_service import ScannerService, ScanResult
import asyncio

class ScanWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list)
    
    def __init__(self, mode: str, scanner: ScannerService, subnet: str = None, port_name: str = None):
        super().__init__()
        self.mode = mode
        self.subnet = subnet
        self.port_name = port_name
        self.scanner = scanner

    def run(self):
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def progress_cb(current, total):
            self.progress.emit(current, total)
            
        try:
            if self.mode == "TCP":
                results = loop.run_until_complete(self.scanner.scan_subnet(self.subnet, progress_cb))
            else:
                # ModbusSerial is sync, but we run in this thread
                results = self.scanner.scan_usb_port(self.port_name, progress_cb)
            self.finished.emit(results)
        except Exception as e:
            print(f"Scanner Worker Error: {e}")
            self.finished.emit([])
        finally:
            loop.close()

class ScannerDialog(QDialog):
    add_device_requested = Signal(dict)  # device params dictionary
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modbus Auto-Discovery")
        self.resize(950, 700)
        
        self.scanner = ScannerService()
        self.all_results = []
        
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- TCP Tab ---
        self.tcp_tab = QWidget()
        self.init_tcp_tab()
        self.tabs.addTab(self.tcp_tab, "Network (TCP)")
        
        # --- USB Tab ---
        self.usb_tab = QWidget()
        self.init_usb_tab()
        self.tabs.addTab(self.usb_tab, "USB (RTU)")

        # Progress (shared or per tab? let's keep it below tabs)
        self.progress_layout = QVBoxLayout()
        self.progress_label = QLabel("Scanner ready.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(self.progress_layout)
        
        # Results table (shared)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Target", "Status", "Modbus Valid", "Latency/Baud", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        main_layout.addWidget(self.table)
        
        # Log viewer (shared)
        main_layout.addWidget(QLabel("<b>Detailed Logs:</b>"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #f8f9fa; font-family: monospace;")
        self.log_display.setMaximumHeight(150)
        main_layout.addWidget(self.log_display)
        
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.worker = None

    def init_tcp_tab(self):
        layout = QVBoxLayout(self.tcp_tab)
        
        subnet_box = QHBoxLayout()
        subnet_box.addWidget(QLabel("Subnet:"))
        self.subnet_input = QLineEdit()
        local_ip = self.scanner.get_local_ip()
        self.subnet_input.setText(self.scanner.get_subnet(local_ip))
        subnet_box.addWidget(self.subnet_input)
        
        self.scan_tcp_btn = QPushButton("Scan Network")
        self.scan_tcp_btn.clicked.connect(self.start_tcp_scan)
        subnet_box.addWidget(self.scan_tcp_btn)
        
        layout.addLayout(subnet_box)
        layout.addStretch()

    def init_usb_tab(self):
        layout = QVBoxLayout(self.usb_tab)
        
        port_box = QHBoxLayout()
        port_box.addWidget(QLabel("Select Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_box.addWidget(self.port_combo, 1)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh_ports)
        port_box.addWidget(refresh_btn)
        
        self.scan_usb_btn = QPushButton("Scan USB")
        self.scan_usb_btn.clicked.connect(self.start_usb_scan)
        port_box.addWidget(self.scan_usb_btn)
        
        layout.addLayout(port_box)
        
        # Diagnostic Button
        self.diag_btn = QPushButton("🆘 Deep Hardware Diagnostic")
        self.diag_btn.setStyleSheet("background-color: #f0883e; color: white; font-weight: bold; padding: 5px;")
        self.diag_btn.clicked.connect(self.open_diagnostic)
        layout.addWidget(self.diag_btn)
        
        layout.addStretch()

    def open_diagnostic(self):
        from ui.hardware_diagnostic_dialog import HardwareDiagnosticDialog
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "No Port", "Please select a COM/USB port first.")
            return
        
        # Use existing logger if available in parent, else None
        logger = getattr(self.parent(), 'logger', None)
        dialog = HardwareDiagnosticDialog(port, logger, self)
        dialog.exec()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = self.scanner.list_com_ports()
        for p in ports:
            self.port_combo.addItem(f"{p['device']} ({p['description']})", p['device'])

    def start_tcp_scan(self):
        subnet = self.subnet_input.text().strip()
        self.start_scan("TCP", subnet=subnet)

    def start_usb_scan(self):
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "No Port", "Please select a COM/USB port first.")
            return
        self.start_scan("RTU", port_name=port)

    def start_scan(self, mode, subnet=None, port_name=None):
        if self.worker and self.worker.isRunning():
            self.scanner.stop()
            return

        self.table.setRowCount(0)
        self.all_results = []
        self.progress_bar.setValue(0)
        self.log_display.clear()
        
        if mode == "TCP":
            self.progress_bar.setRange(0, 254)
        else:
            self.progress_bar.setRange(0, 5) # 5 common baud rates
            
        self.worker = ScanWorker(mode, self.scanner, subnet=subnet, port_name=port_name)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        
        self.current_scan_mode = mode

    def on_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Scanning... {current}/{total} checked")

    def on_finished(self, results):
        self.all_results = results
        self.progress_label.setText(f"Scan complete. Found {len([r for r in results if r.is_online])} reachable configurations.")
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
            
            ip_item = QTableWidgetItem(res.ip if res.ip else res.port_name)
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
            
            if res.ip:
                latency = f"{res.response_time:.1f} ms" if res.response_time > 0 else "-"
            else:
                latency = f"{res.baud_rate} baud"
            self.table.setItem(row, 3, QTableWidgetItem(latency))
            
            add_btn = QPushButton("Use Config")
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
        if res.ip:
            self.add_device_requested.emit({"connection_type": "TCP", "ip_address": res.ip, "port": 502})
        else:
            self.add_device_requested.emit({"connection_type": "RTU", "com_port": res.port_name, "baud_rate": res.baud_rate})

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
