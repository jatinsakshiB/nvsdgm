from typing import Dict, List
from models.device import Device
from modbus.modbus_client import ModbusClientBase
from modbus.rtu_client import RTUClient
from modbus.tcp_client import TCPClient
from services.logging_service import AppLogger
from database.sqlite_manager import SQLiteManager

class DeviceService:
    def __init__(self, db: SQLiteManager, logger: AppLogger):
        self.db = db
        self.logger = logger
        # device_id -> ModbusClientBase instance
        self.clients: Dict[int, ModbusClientBase] = {}

    def initialize_from_db(self):
        """Load all enabled devices from DB and attempt initial connections."""
        devices = self.db.get_devices()
        for device in devices:
            if device.is_enabled and device.id is not None:
                self.add_client(device)

    def add_client(self, device: Device):
        if device.id in self.clients:
            return  # Already exists

        client = None
        if device.connection_type == "RTU":
            client = RTUClient(device)
        elif device.connection_type == "TCP":
            client = TCPClient(device)
        else:
            self.logger.error(f"Unknown connection type {device.connection_type} for device {device.name}", "DeviceService")
            return

        # Attempt to connect immediately (optional, or let polling service do it)
        if client.connect():
            self.logger.info(f"Successfully connected to '{device.name}'", "DeviceService")
        else:
            self.logger.warning(f"Failed to connect to '{device.name}' on initialization", "DeviceService")

        self.clients[device.id] = client

    def remove_client(self, device_id: int):
        if device_id in self.clients:
            client = self.clients[device_id]
            client.disconnect()
            del self.clients[device_id]
            self.logger.info(f"Removed client for device ID {device_id}", "DeviceService")

    def get_client(self, device_id: int) -> ModbusClientBase:
        return self.clients.get(device_id)

    def get_all_clients(self) -> List[ModbusClientBase]:
        return list(self.clients.values())

    def update_client(self, device: Device):
        """Update a device connection if settings changed."""
        if device.id in self.clients:
            self.remove_client(device.id)
            
        if device.is_enabled:
            self.add_client(device)
