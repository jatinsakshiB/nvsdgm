from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
from PySide6.QtCore import Slot, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtCore import Slot, Qt
from database.sqlite_manager import SQLiteManager
from services.device_service import DeviceService
from modbus.parser import ModbusParser

class DashboardWidget(QWidget):
    def __init__(self, db: SQLiteManager, device_service: DeviceService, parent=None):
        super().__init__(parent)
        self.db = db
        self.device_service = device_service
        self.current_device_id = None
        
        # UI Elements Map: Register ID -> row index
        self.row_map = {}
        
        # Previous values Map: Register ID -> col_name -> value
        self.previous_values = {}
        
        layout = QVBoxLayout(self)
        
        # Top Bar
        top_bar = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 14px;")
        
        top_bar.addWidget(QLabel("Select Device:"))
        top_bar.addWidget(self.device_combo)
        top_bar.addStretch()
        top_bar.addWidget(self.status_label)
        layout.addLayout(top_bar)
        
        # Search Bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Address, Name, or Value...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table for Live Data
        self.table = QTableWidget()
        self.columns = ["Address", "Name", "Unit", "int16", "uint16", "int32", "uint32", "float16", "float32"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        self.refresh_devices()

    def refresh_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        devices = self.db.get_devices()
        for d in devices:
            if d.is_enabled:
                self.device_combo.addItem(d.name, userData=d.id)
        
        if self.device_combo.count() > 0:
            self.current_device_id = self.device_combo.currentData()
            self._build_table()
        else:
            self.table.setRowCount(0)
            self.row_map.clear()
        self.device_combo.blockSignals(False)

    def on_device_selected(self, index):
        if index >= 0:
            self.current_device_id = self.device_combo.itemData(index)
            self._build_table()

    def _build_table(self):
        self.table.setRowCount(0)
        self.row_map.clear()
        self.previous_values.clear()

        if not self.current_device_id:
            return

        # Check initial connection status
        client = self.device_service.get_client(self.current_device_id)
        is_connected = client.is_connected if client else False
        self.on_connection_status_changed(self.current_device_id, is_connected)

        registers = self.db.get_registers(self.current_device_id)
        
        for reg in registers:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(reg.address)))
            self.table.setItem(row, 1, QTableWidgetItem(reg.name))
            self.table.setItem(row, 2, QTableWidgetItem(reg.unit))
            
            # Init empty items for values
            for col in range(3, len(self.columns)):
                item = QTableWidgetItem("---")
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
            
            self.row_map[reg.id] = row
            self.previous_values[reg.id] = {}
            
        # Re-apply search if exists
        self.on_search(self.search_input.text())

    @Slot(int, bool)
    def on_connection_status_changed(self, device_id: int, is_connected: bool):
        if device_id == self.current_device_id:
            if is_connected:
                self.status_label.setText("Status: Connected")
                self.status_label.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 14px;")
            else:
                self.status_label.setText("Status: Disconnected / Error")
                self.status_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 14px;")

    @Slot(str)
    def on_search(self, text):
        search_text = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    @Slot(str, int, int, object)
    def on_raw_data_polled(self, timestamp: str, device_id: int, register_id: int, raw_data: list):
        if device_id == self.current_device_id:
            if register_id in self.row_map:
                row = self.row_map[register_id]
                
                # Fetch device to get endianness
                client = self.device_service.get_client(device_id)
                device = client.device if client else None
                from pymodbus.constants import Endian
                b_order = Endian.LITTLE if getattr(device, 'byte_order', 'BIG') == 'LITTLE' else Endian.BIG
                w_order = Endian.LITTLE if getattr(device, 'word_order', 'BIG') == 'LITTLE' else Endian.BIG
                
                # Parse all formats
                results = ModbusParser.parse_all(raw_data, byteorder=b_order, wordorder=w_order)
                
                # Update cells
                for i, col_name in enumerate(self.columns[3:], start=3):
                    val = results.get(col_name)
                    item = self.table.item(row, i)
                    if item:
                        if val is not None:
                            # Determine blink color
                            prev_val = self.previous_values[register_id].get(col_name)
                            if prev_val is not None and val != prev_val:
                                if val > prev_val:
                                    item.setBackground(QColor("#1e4620")) # Dark Green
                                else:
                                    item.setBackground(QColor("#4e1c1c")) # Dark Red
                                
                                # Setup timer to clear background
                                QTimer.singleShot(500, lambda it=item: it.setBackground(QColor("transparent")) if it else None)
                                
                            self.previous_values[register_id][col_name] = val
                            
                            item.setText(f"{val:.2f}")
                            item.setForeground(Qt.white)
                        else:
                            item.setText("N/A")
                            item.setForeground(Qt.gray)
