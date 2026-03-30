from PySide6.QtCore import QObject, Signal
import datetime
from database.sqlite_manager import SQLiteManager

class AppLogger(QObject):
    # Signal emitted when a new log is created: level, timestamp, message, source
    new_log = Signal(str, str, str, str)

    def __init__(self, db: SQLiteManager):
        super().__init__()
        self.db = db

    def _log(self, level: str, message: str, source: str = "System"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.db.add_log(level=level, message=message, source=source)
        except Exception as e:
            print(f"Failed to log to DB: {e}")
        
        print(f"[{timestamp}] [{level}] [{source}] {message}")
        self.new_log.emit(level, timestamp, message, source)

    def info(self, message: str, source: str = "System"):
        self._log("INFO", message, source)

    def warning(self, message: str, source: str = "System"):
        self._log("WARNING", message, source)

    def error(self, message: str, source: str = "System"):
        self._log("ERROR", message, source)
