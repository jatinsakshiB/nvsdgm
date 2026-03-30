from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QLineEdit, 
    QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from database.sqlite_manager import SQLiteManager
from models.device import Device
from services.device_service import DeviceService
from ui.scanner_dialog import ScannerDialog
import pandas as pd # used later if needed

class DeviceDialog(QDialog):
    def __init__(self, device: Device = None, initial_ip: str = None, initial_port: int = 502, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Device Configuration")
        self.setMinimumWidth(400)
        self.device = device
        self.initial_ip = initial_ip
        self.initial_port = initial_port
        
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["TCP", "RTU"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        
        self.enabled_chk = QCheckBox("Enabled")
        self.enabled_chk.setChecked(True)
        self.slave_input = QLineEdit("1")
        
        # RTU fields
        self.com_input = QLineEdit()
        self.baud_input = QLineEdit("9600")
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["N", "E", "O"])
        self.stop_input = QLineEdit("1")
        
        # TCP fields
        self.ip_input = QLineEdit()
        self.port_input = QLineEdit("502")
        
        layout.addRow("Name:", self.name_input)
        layout.addRow("Type:", self.type_combo)
        layout.addRow("", self.enabled_chk)
        layout.addRow("Slave ID:", self.slave_input)
        
        layout.addRow("--- TCP Settings ---", QWidget())
        layout.addRow("IP Address:", self.ip_input)
        layout.addRow("Port:", self.port_input)
        
        layout.addRow("--- RTU Settings ---", QWidget())
        layout.addRow("COM Port:", self.com_input)
        layout.addRow("Baud Rate:", self.baud_input)
        layout.addRow("Parity:", self.parity_combo)
        layout.addRow("Stop Bits:", self.stop_input)
        
        btn_layout = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        test_btn.setStyleSheet("background-color: #3498db; color: white;")
        test_btn.clicked.connect(self.on_test)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #238636; color: white;")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(test_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)
        
        if self.device:
            self.load_device()
        elif self.initial_ip:
            self.ip_input.setText(self.initial_ip)
            self.port_input.setText(str(self.initial_port))
            
        self.on_type_changed(self.type_combo.currentText())

    def on_type_changed(self, ctype):
        is_tcp = (ctype == "TCP")
        self.ip_input.setEnabled(is_tcp)
        self.port_input.setEnabled(is_tcp)
        
        is_rtu = (ctype == "RTU")
        self.com_input.setEnabled(is_rtu)
        self.baud_input.setEnabled(is_rtu)
        self.parity_combo.setEnabled(is_rtu)
        self.stop_input.setEnabled(is_rtu)

    def load_device(self):
        self.name_input.setText(self.device.name)
        self.type_combo.setCurrentText(self.device.connection_type)
        self.enabled_chk.setChecked(self.device.is_enabled)
        self.slave_input.setText(str(self.device.slave_id))
        
        if self.device.connection_type == "TCP":
            self.ip_input.setText(self.device.ip_address or "")
            self.port_input.setText(str(self.device.port or 502))
        else:
            self.com_input.setText(self.device.com_port or "")
            self.baud_input.setText(str(self.device.baud_rate or 9600))
            self.parity_combo.setCurrentText(self.device.parity or "N")
            self.stop_input.setText(str(self.device.stop_bits or 1))

    def get_device(self) -> Device:
        dev = Device(
            name=self.name_input.text(),
            connection_type=self.type_combo.currentText(),
            is_enabled=self.enabled_chk.isChecked(),
            slave_id=int(self.slave_input.text() or 1),
            id=self.device.id if self.device else None
        )
        if dev.connection_type == "TCP":
            dev.ip_address = self.ip_input.text()
            dev.port = int(self.port_input.text() or 502)
        else:
            dev.com_port = self.com_input.text()
            dev.baud_rate = int(self.baud_input.text() or 9600)
            dev.parity = self.parity_combo.currentText()
            dev.stop_bits = int(self.stop_input.text() or 1)
        return dev

    def on_test(self):
        from services.scanner_service import ScannerService
        ctype = self.type_combo.currentText()
        if ctype != "TCP":
            QMessageBox.information(self, "Test", "Test connection is currently implemented for TCP only.")
            return
            
        ip = self.ip_input.text().strip()
        port_str = self.port_input.text().strip()
        if not ip or not port_str:
            QMessageBox.warning(self, "Error", "IP and Port are required for testing.")
            return
            
        try:
            port = int(port_str)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid Port number.")
            return

        self.setCursor(Qt.WaitCursor)
        scanner = ScannerService()
        result = scanner.test_connection(ip, port)
        self.unsetCursor()
        
        msg = f"<b>Result: {result.status_msg}</b><br><br>"
        msg += "<br>".join(result.logs).replace("\n", "<br>")
        
        QMessageBox.information(self, "Test Diagnostic", msg)


class DeviceManagerWidget(QWidget):
    devices_changed = Signal()

    def __init__(self, db: SQLiteManager, device_service: DeviceService = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.device_service = device_service
        
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Device")
        add_btn.clicked.connect(self.on_add)
        edit_btn = QPushButton("Edit Device")
        edit_btn.clicked.connect(self.on_edit)
        del_btn = QPushButton("Delete Device")
        del_btn.clicked.connect(self.on_delete)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_data)
        
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(del_btn)
        toolbar.addWidget(refresh_btn)
        
        toolbar.addSpacing(20)
        scan_btn = QPushButton("Scan Network")
        scan_btn.setStyleSheet("background-color: #238636; color: white; font-weight: bold;")
        scan_btn.clicked.connect(self.on_scan)
        toolbar.addWidget(scan_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Type", "Status", "Target", "Slave"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        devices = self.db.get_devices()
        self.table.setRowCount(0)
        for dev in devices:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(dev.id)))
            self.table.setItem(row, 1, QTableWidgetItem(dev.name))
            self.table.setItem(row, 2, QTableWidgetItem(dev.connection_type))
            self.table.setItem(row, 3, QTableWidgetItem("Enabled" if dev.is_enabled else "Disabled"))
            
            target = f"{dev.ip_address}:{dev.port}" if dev.connection_type == "TCP" else f"{dev.com_port} ({dev.baud_rate})"
            self.table.setItem(row, 4, QTableWidgetItem(target))
            self.table.setItem(row, 5, QTableWidgetItem(str(dev.slave_id)))
            
            # Update status with real-time connection info if available
            if self.device_service and dev.is_enabled:
                client = self.device_service.get_client(dev.id)
                if client and client.is_connected:
                    status_item = QTableWidgetItem("✅ Connected")
                    status_item.setForeground(Qt.green)
                    self.table.setItem(row, 3, status_item)
                else:
                    status_item = QTableWidgetItem("❌ Disconnected")
                    status_item.setForeground(Qt.red)
                    self.table.setItem(row, 3, status_item)

    def on_scan(self):
        dialog = ScannerDialog(self)
        dialog.add_device_requested.connect(self.on_add_from_scan)
        dialog.exec()

    def on_add_from_scan(self, ip, port):
        # Open the standard Add dialog but with IP/Port pre-filled
        dialog = DeviceDialog(initial_ip=ip, initial_port=port, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                new_dev = dialog.get_device()
                new_dev.validate()
                self.db.add_device(new_dev)
                self.load_data()
                self.devices_changed.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def on_add(self):
        dialog = DeviceDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                new_dev = dialog.get_device()
                new_dev.validate()
                self.db.add_device(new_dev)
                self.load_data()
                self.devices_changed.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def on_edit(self):
        sel = self.table.selectedItems()
        if not sel: return
        dev_id = int(self.table.item(sel[0].row(), 0).text())
        
        # Find device obj
        devices = self.db.get_devices()
        dev = next((d for d in devices if d.id == dev_id), None)
        if not dev: return
        
        dialog = DeviceDialog(device=dev, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                updated_dev = dialog.get_device()
                updated_dev.validate()
                self.db.update_device(updated_dev)
                self.load_data()
                self.devices_changed.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def on_delete(self):
        sel = self.table.selectedItems()
        if not sel: return
        dev_id = int(self.table.item(sel[0].row(), 0).text())
        
        reply = QMessageBox.question(self, "Delete", f"Are you sure you want to delete Device ID {dev_id}?\nThis removes history and registers associated too.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_device(dev_id)
            self.load_data()
            self.devices_changed.emit()
