from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel
from PySide6.QtCore import Slot
import pyqtgraph as pg
import datetime
from database.sqlite_manager import SQLiteManager

class RealTimeChartWidget(QWidget):
    def __init__(self, db: SQLiteManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_device_id = None
        
        # register_id -> { 'x': [], 'y': [], 'curve': pg.PlotDataItem }
        self.plot_data = {}
        self.colors = ['#58a6ff', '#3fb950', '#ff7b72', '#d2a8ff', '#f0883e', '#79c0ff', '#8b949e']
        
        layout = QVBoxLayout(self)
        
        # Toolbar
        top_bar = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        
        top_bar.addWidget(QLabel("Select Device:"))
        top_bar.addWidget(self.device_combo)
        top_bar.addStretch()
        layout.addLayout(top_bar)
        
        # Chart setup
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#0d1117')
        self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Add a DateAxisItem for X-axis
        self.x_axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget.setAxisItems({'bottom': self.x_axis})
        
        layout.addWidget(self.plot_widget)
        
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
            self._setup_plot()
        self.device_combo.blockSignals(False)

    def on_device_selected(self, index):
        if index >= 0:
            self.current_device_id = self.device_combo.itemData(index)
            self._setup_plot()

    def _setup_plot(self):
        self.plot_widget.clear()
        self.plot_data.clear()
        
        if not self.current_device_id:
            return
            
        registers = self.db.get_registers(self.current_device_id)
        
        for i, reg in enumerate(registers):
            color = self.colors[i % len(self.colors)]
            curve = self.plot_widget.plot(name=reg.name, pen=pg.mkPen(color=color, width=2))
            
            self.plot_data[reg.id] = {
                'x': [],
                'y': [],
                'curve': curve
            }
            
            # Load last 100 historical points to prepopulate chart seamlessly
            history = self.db.get_history(self.current_device_id, reg.id, limit=50)
            for ts_str, val in history:
                # convert "YYYY-MM-DD HH:MM:SS" to timestamp float
                dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                self.plot_data[reg.id]['x'].append(dt.timestamp())
                self.plot_data[reg.id]['y'].append(val)
                
            if self.plot_data[reg.id]['x']:
                curve.setData(self.plot_data[reg.id]['x'], self.plot_data[reg.id]['y'])

    @Slot(str, int, int, float)
    def on_data_polled(self, timestamp_str: str, device_id: int, register_id: int, value: float):
        if device_id == self.current_device_id:
            if register_id in self.plot_data:
                dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                ts = dt.timestamp()
                
                pd = self.plot_data[register_id]
                pd['x'].append(ts)
                pd['y'].append(value)
                
                # Keep last N points (e.g., 60 points for 1 minute window, or up to 300 for 5 min)
                MAX_POINTS = 300
                if len(pd['x']) > MAX_POINTS:
                    pd['x'] = pd['x'][-MAX_POINTS:]
                    pd['y'] = pd['y'][-MAX_POINTS:]
                    
                pd['curve'].setData(pd['x'], pd['y'])
