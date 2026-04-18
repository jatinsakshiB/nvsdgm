import sys
import os
import json
import urllib.request

from PySide6.QtWidgets import QApplication, QMessageBox
from database.sqlite_manager import SQLiteManager
from services.logging_service import AppLogger
from services.device_service import DeviceService
from services.polling_service import PollingService
from ui.main_window import MainWindow

def check_authorization():
    try:
        req = urllib.request.Request("https://jbdev.in/api/check/nvsdgm", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data.get("status") is True:
                return True
    except Exception as e:
        print(f"Authorization check failed: {e}")
    return False

def get_app_data_path():
    """Returns the platform-specific path to store application data."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    
    path = os.path.join(base, "NVSDGM")
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def main():
    # Use persistent AppData for the database
    data_dir = get_app_data_path()
    db_path = os.path.join(data_dir, "gas_analyzer.db")
    
    app = QApplication(sys.argv)
    app.setApplicationName("NVSDGM")
    
    # --- Single Instance Guard ---
    from PySide6.QtCore import QLockFile
    lock_file_path = os.path.join(data_dir, "nvsdgm.lock")
    lock_file = QLockFile(lock_file_path)
    
    if not lock_file.tryLock(100): # Try for 100ms
        QMessageBox.critical(None, "Already Running", 
                             "Another instance of NVSDGM is already running.\n"
                             "Please close it or check Task Manager/Activity Monitor and try again.")
        sys.exit(1)
    
    if not check_authorization():
        QMessageBox.critical(None, "Error", "Internet error or service disabled. Please check your connection or contact support.")
        sys.exit(1)
        
    # 1. Init Database Layer
    db = SQLiteManager(db_path)
    
    # 2. Init Logger Service
    logger = AppLogger(db)
    logger.info("Application starting...", "System")
    
    # 3. Init Device Service
    device_service = DeviceService(db, logger)
    device_service.initialize_from_db()  # Loads enabled devices and attempts initial connections
    
    # 4. Init Polling Service
    polling_service = PollingService(db, device_service, logger, poll_interval_ms=1000)
    polling_service.start()  # Starts the background QThread
    
    # 5. UI Layer
    window = MainWindow(db, logger, device_service, polling_service)
    window.show()
    
    try:
        sys.exit(app.exec())
    finally:
        logger.info("Application shutdown...", "System")
        polling_service.stop()

if __name__ == "__main__":
    main()
