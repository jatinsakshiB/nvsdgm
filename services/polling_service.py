import time
import datetime
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker
from PySide6.QtWidgets import QApplication

from database.sqlite_manager import SQLiteManager
from services.device_service import DeviceService
from services.logging_service import AppLogger
from modbus.parser import ModbusParser

class PollingService(QThread):
    # Signals
    # timestamp, device_id, register_id, value
    data_polled = Signal(str, int, int, float)
    
    # device_id, status (True for connected, False for disconnected)
    connection_status_changed = Signal(int, bool)

    def __init__(self, db: SQLiteManager, device_service: DeviceService, logger: AppLogger, poll_interval_ms: int = 1000):
        super().__init__()
        self.db = db
        self.device_service = device_service
        self.logger = logger
        self.poll_interval_ms = poll_interval_ms
        self._is_running = False
        self._mutex = QMutex()

    def run(self):
        with QMutexLocker(self._mutex):
            self._is_running = True
            
        self.logger.info("Polling service started...", "PollingService")

        while self.is_running():
            loop_start = time.time()
            
            self._poll_all_devices()
            
            # Calculate sleep to maintain interval
            elapsed_ms = (time.time() - loop_start) * 1000
            sleep_ms = self.poll_interval_ms - elapsed_ms
            if sleep_ms > 0:
                self.msleep(int(sleep_ms))
            else:
                self.logger.warning(f"Polling loop took longer ({elapsed_ms:.1f}ms) than interval ({self.poll_interval_ms}ms)!", "PollingService")

        self.logger.info("Polling service stopped.", "PollingService")

    def _poll_all_devices(self):
        clients = self.device_service.get_all_clients()
        
        for client in clients:
            if not self.is_running():
                break

            device = client.device
            device_id = device.id
            
            was_connected = client.is_connected
            
            # Check connection, reconnect if needed
            if not client.is_connected:
                client.connect()
                
            if client.is_connected != was_connected:
                status_str = "CONNECTED" if client.is_connected else "DISCONNECTED"
                self.logger.info(f"Device '{device.name}' is now {status_str}", "PollingService")
                self.connection_status_changed.emit(device_id, client.is_connected)

            if not client.is_connected:
                continue # Skip polling if offline

            # Get registers for this device
            registers = self.db.get_registers(device_id)
            if not registers:
                continue

            # In a production app, we would batch reads into single requests (e.g. read consecutive registers)
            # For simplicity, we can read them sequentially. PyModbus handles short contiguous loops quickly enough locally,
            # but to ensure strict adherence to "professional build" we should ideally batch.
            # To keep it reliable first, we will iterate and poll individually.
            # (In a true SCADA app with 10k registers we batch. Here with few gases + temp, individual is fine for v1.)
            
            for reg in registers:
                if not self.is_running():
                    break
                    
                reg_count = ModbusParser.get_register_count(reg.data_type)
                
                # Read from Modbus
                raw_data = client.read_registers(
                    address=reg.address,
                    count=reg_count,
                    function_code=reg.function_code
                )
                
                if raw_data:
                    try:
                        # Parse
                        parsed_val = ModbusParser.parse(raw_data, reg.data_type)
                        # Scale
                        final_val = parsed_val * reg.scaling_factor
                        
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Emit to UI
                        self.data_polled.emit(timestamp, device_id, reg.id, final_val)
                        
                        # Save to DB
                        self.db.add_history(device_id, reg.id, final_val)
                        
                    except Exception as e:
                        self.logger.error(f"Error parsing data for device {device.name} reg {reg.name}: {e}", "PollingService")
                else:
                    self.logger.warning(f"Failed to read register {reg.name} on {device.name}", "PollingService")
                    # Emitting failure state could also trigger a disconnection event if it fails multiple times
                    # For now, mark as disconnected if read fails (simple error handling)
                    client.disconnect()
                    self.connection_status_changed.emit(device_id, False)
                    break # Stop reading further registers for this disconnected device

    def stop(self):
        with QMutexLocker(self._mutex):
            self._is_running = False
        self.wait()

    def is_running(self):
        with QMutexLocker(self._mutex):
            return self._is_running
