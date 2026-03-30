from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PySide6.QtCore import Slot

class LogsPanelWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # Apply premium dark theme styling to logs
        self.text_edit.setStyleSheet("background-color: #0d1117; color: #e6edf3; font-family: 'Consolas', 'Courier New', monospace; border: 1px solid #30363d; border-radius: 6px; padding: 8px;")
        layout.addWidget(self.text_edit)
        
    @Slot(str, str, str, str)
    def on_new_log(self, level: str, timestamp: str, message: str, source: str):
        color = "#e6edf3"
        if level == "ERROR":
            color = "#f85149"
        elif level == "WARNING":
            color = "#d29922"
        elif level == "INFO":
            color = "#3fb950"
            
        line = f'<span style="color: #8b949e;">[{timestamp}]</span> <span style="color: {color}; font-weight: bold;">[{level}]</span> <span style="color: #58a6ff;">[{source}]</span> {message}'
        self.text_edit.append(line)
