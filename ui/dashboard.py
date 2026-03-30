from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QComboBox
from PySide6.QtCore import Slot, Qt
from database.sqlite_manager import SQLiteManager
from services.device_service import DeviceService

class DashboardWidget(QWidget):
    def __init__(self, db: SQLiteManager, device_service: DeviceService, parent=None):
        super().__init__(parent)
        self.db = db
        self.device_service = device_service
        self.current_device_id = None
        
        # UI Elements Map: Register ID -> QLabel for value
        self.value_labels = {}
        
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
        
        # Grid for Live Cards
        self.grid_layout = QGridLayout()
        layout.addLayout(self.grid_layout)
        layout.addStretch()
        
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
            self._build_cards()
        self.device_combo.blockSignals(False)

    def on_device_selected(self, index):
        if index >= 0:
            self.current_device_id = self.device_combo.itemData(index)
            self._build_cards()

    def _build_cards(self):
        # Clear grid
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self.value_labels.clear()

        if not self.current_device_id:
            return

        registers = self.db.get_registers(self.current_device_id)
        
        row, col = 0, 0
        for reg in registers:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;")
            card_layout = QVBoxLayout(card)
            
            title = QLabel(reg.name)
            title.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: 600; text-transform: uppercase;")
            title.setAlignment(Qt.AlignCenter)
            
            value = QLabel("---")
            value.setStyleSheet("color: #58a6ff; font-size: 32px; font-weight: bold;")
            value.setAlignment(Qt.AlignCenter)
            
            unit = QLabel(reg.unit)
            unit.setStyleSheet("color: #8b949e; font-size: 13px;")
            unit.setAlignment(Qt.AlignCenter)
            
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            card_layout.addWidget(unit)
            
            self.grid_layout.addWidget(card, row, col)
            self.value_labels[reg.id] = (value, reg.unit)
            
            col += 1
            if col > 3:
                col = 0
                row += 1

    @Slot(int, bool)
    def on_connection_status_changed(self, device_id: int, is_connected: bool):
        if device_id == self.current_device_id:
            if is_connected:
                self.status_label.setText("Status: Connected")
                self.status_label.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 14px;")
            else:
                self.status_label.setText("Status: Disconnected / Error")
                self.status_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 14px;")
                # If disconnected, maybe show "---" or keep last value
                
    @Slot(str, int, int, float)
    def on_data_polled(self, timestamp: str, device_id: int, register_id: int, value: float):
        if device_id == self.current_device_id:
            if register_id in self.value_labels:
                label, unit = self.value_labels[register_id]
                label.setText(f"{value:.2f}")
