from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QLabel
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from ui.dashboard import DashboardWidget
from ui.device_manager import DeviceManagerWidget
from ui.register_manager import RegisterManagerWidget
from ui.charts import RealTimeChartWidget
from ui.logs_panel import LogsPanelWidget

from database.sqlite_manager import SQLiteManager
from services.logging_service import AppLogger
from services.device_service import DeviceService
from services.polling_service import PollingService

class MainWindow(QMainWindow):
    def __init__(self, db: SQLiteManager, logger: AppLogger, device_service: DeviceService, polling_service: PollingService):
        super().__init__()
        self.setWindowTitle("NVSDGM")
        self.resize(1200, 800)
        self.db = db
        self.logger = logger
        self.device_service = device_service
        self.polling_service = polling_service
        
        # Apply premium modern dark theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; }
            QWidget { color: #e6edf3; font-family: 'Inter', 'Segoe UI', sans-serif; }
            QPushButton { 
                background-color: #21262d; color: #e6edf3; border: 1px solid #30363d; 
                padding: 10px; border-radius: 6px; text-align: left; padding-left: 15px; font-weight: 600;
            }
            QPushButton:hover { background-color: #30363d; border-color: #8b949e; }
            QPushButton:pressed { background-color: #282e33; }
            QTableWidget { background-color: #161b22; gridline-color: #30363d; border: 1px solid #30363d; border-radius: 6px; }
            QHeaderView::section { background-color: #21262d; padding: 6px; border: none; border-bottom: 2px solid #30363d; border-right: 1px solid #30363d; font-weight: bold; }
            QLineEdit, QComboBox, QSpinBox { background-color: #0d1117; border: 1px solid #30363d; padding: 6px; border-radius: 6px; color: #e6edf3; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #58a6ff; }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #30363d;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: #161b22;
            }
            QComboBox::down-arrow {
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23e6edf3' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>");
                width: 16px;
                height: 16px;
            }
            QComboBox::down-arrow:on, QComboBox::down-arrow:hover {
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2358a6ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>");
            }
            QComboBox QAbstractItemView {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #e6edf3;
                selection-background-color: #21262d;
                selection-color: #58a6ff;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            
            QMessageBox { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
            QMessageBox QLabel { color: #e6edf3; }
            QDialog { background-color: #0d1117; color: #e6edf3; }
            QDialog QLabel { color: #e6edf3; }
            QScrollBar:vertical { background-color: #0d1117; width: 12px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background-color: #30363d; min-height: 20px; border-radius: 6px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #161b22; border-right: 1px solid #30363d;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 20)
        
        # Title
        title_lbl = QLabel("NVSDGM")
        title_lbl.setStyleSheet("font-size: 28px; font-weight: 900; color: #58a6ff; letter-spacing: 3px; text-align: center; padding-top: 10px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(title_lbl)
        sidebar_layout.addSpacing(40)
        
        # Buttons
        self.btn_dashboard = QPushButton("Dashboard")
        self.btn_devices = QPushButton("Devices")
        self.btn_registers = QPushButton("Registers")
        self.btn_charts = QPushButton("Charts")
        self.btn_logs = QPushButton("Logs")
        
        for btn in [self.btn_dashboard, self.btn_devices, self.btn_registers, self.btn_charts, self.btn_logs]:
            sidebar_layout.addWidget(btn)
        sidebar_layout.addStretch()
        
        main_layout.addWidget(sidebar)
        
        # Stacked Widget Workspace
        self.workspace = QStackedWidget()
        main_layout.addWidget(self.workspace)
        
        # Init Pages
        self.page_dashboard = DashboardWidget(self.db, self.device_service)
        self.page_devices = DeviceManagerWidget(self.db, self.device_service)
        self.page_registers = RegisterManagerWidget(self.db, self.device_service)
        self.page_charts = RealTimeChartWidget(self.db)
        self.page_logs = LogsPanelWidget()
        
        self.workspace.addWidget(self.page_dashboard)
        self.workspace.addWidget(self.page_devices)
        self.workspace.addWidget(self.page_registers)
        self.workspace.addWidget(self.page_charts)
        self.workspace.addWidget(self.page_logs)
        
        # Signals wiring
        self.btn_dashboard.clicked.connect(lambda: self.workspace.setCurrentIndex(0))
        self.btn_devices.clicked.connect(lambda: self.workspace.setCurrentIndex(1))
        self.btn_registers.clicked.connect(lambda: self.workspace.setCurrentIndex(2))
        self.btn_charts.clicked.connect(lambda: self.workspace.setCurrentIndex(3))
        self.btn_logs.clicked.connect(lambda: self.workspace.setCurrentIndex(4))
        
        # Events wiring
        self.page_devices.devices_changed.connect(self.on_devices_changed)
        self.page_registers.registers_changed.connect(self.on_registers_changed)
        
        self.logger.new_log.connect(self.page_logs.on_new_log)
        self.polling_service.data_polled.connect(self.page_dashboard.on_data_polled)
        self.polling_service.data_polled.connect(self.page_charts.on_data_polled)
        
        self.polling_service.connection_status_changed.connect(self.page_dashboard.on_connection_status_changed)
        self.polling_service.connection_status_changed.connect(self.page_devices.load_data)

    def on_devices_changed(self):
        # Full reload of device connections
        # Simple approach for demonstration: re-eval active connections
        for dev in self.db.get_devices():
            self.device_service.update_client(dev)
        
        self.page_dashboard.refresh_devices()
        self.page_charts.refresh_devices()

    def on_registers_changed(self):
        self.page_dashboard.refresh_devices()
        self.page_charts.refresh_devices()

    def closeEvent(self, event):
        self.polling_service.stop()
        super().closeEvent(event)
