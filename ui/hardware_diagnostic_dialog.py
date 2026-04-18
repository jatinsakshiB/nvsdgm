from typing import Any, Optional, Dict
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar, 
    QLabel, QComboBox, QTextEdit, QFrame
)
from services.scanner_service import ScannerService

class DiagnosticWorker(QThread):
    progress = Signal(int, int)
    new_log = Signal(str)
    finished = Signal(dict) # result dict or None
    
    def __init__(self, scanner: ScannerService, port: str, global_logger: Any = None):
        super().__init__()
        self.scanner = scanner
        self.port = port
        self.global_logger = global_logger

    def run(self):
        def progress_cb(current, total):
            self.progress.emit(current, total)
            
        def log_cb(msg):
            self.new_log.emit(msg)
            
        result = self.scanner.diagnostic_sweep(
            self.port, progress_cb, log_cb, self.global_logger
        )
        self.finished.emit(result or {})

class HardwareDiagnosticDialog(QDialog):
    def __init__(self, port: str, logger: Any = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hardware Diagnostic & Deep Scan")
        self.resize(600, 700)
        self.port = port
        self.logger = logger
        self.scanner = ScannerService()
        self.worker = None

        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("🔍 Modbus Hardware Diagnostic")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(header)
        
        info = QLabel(f"Target Port: <b>{port}</b>")
        layout.addWidget(info)
        
        # Troubleshooting Guide Panel
        guide_frame = QFrame()
        guide_frame.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px;")
        guide_layout = QVBoxLayout(guide_frame)
        
        guide_title = QLabel("⚠️ Troubleshooting Checklist:")
        guide_title.setStyleSheet("font-weight: bold; color: #f0883e;")
        guide_layout.addWidget(guide_title)
        
        guide_text = QLabel(
            "1. <b>Wiring</b>: Are A(+) and B(-) wires reversed? (Classic RS485 issue)\n"
            "2. <b>Power</b>: Is the device powered and showing a run/com LED?\n"
            "3. <b>Ground</b>: Is the signal ground shared if using long cables?\n"
            "4. <b>Terminating Resistor</b>: Is it 120 ohms? (needed for long distances)"
        )
        guide_text.setWordWrap(True)
        guide_layout.addWidget(guide_text)
        
        layout.addWidget(guide_frame)
        
        # Progress
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log Panel
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #010409; color: #7ee787; font-family: monospace;")
        layout.addWidget(self.log_display)
        
        # Found Result Panel
        self.result_lbl = QLabel("")
        self.result_lbl.setStyleSheet("font-weight: bold; color: #58a6ff; font-size: 14px;")
        layout.addWidget(self.result_lbl)
        
        # Actions
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Start Deep Scan")
        self.scan_btn.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 10px;")
        self.scan_btn.clicked.connect(self.start_diagnostic)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def add_log(self, msg):
        self.log_display.append(msg)
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())

    def start_diagnostic(self):
        if self.worker and self.worker.isRunning():
            self.scanner.stop()
            self.scan_btn.setText("Stopping...")
            self.scan_btn.setEnabled(False)
            return

        self.log_display.clear()
        self.result_lbl.setText("")
        self.progress_bar.setValue(0)
        self.scan_btn.setText("Stop Scan")
        self.scan_btn.setStyleSheet("background-color: #da3633; color: white; font-weight: bold; padding: 10px;")
        
        self.worker = DiagnosticWorker(self.scanner, self.port, self.logger)
        self.worker.progress.connect(self.on_progress)
        self.worker.new_log.connect(self.add_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, current, total):
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))

    def on_finished(self, result):
        self.scan_btn.setText("Start Deep Scan")
        self.scan_btn.setEnabled(True)
        self.scan_btn.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 10px;")
        
        if result:
            msg = (f"🎯 DEVICE FOUND!\n"
                   f"Baud Rate: {result['baud']}\n"
                   f"Parity: {result['parity']}\n"
                   f"Slave ID: {result['slave']}")
            self.result_lbl.setText(msg)
            self.add_log(f"\n✅ SUCCESS: Found device at {result['baud']}/ {result['parity']} / ID {result['slave']}")
        else:
            if not self.scanner._stop_requested:
                self.result_lbl.setText("❌ No device detected. Check wiring.")
