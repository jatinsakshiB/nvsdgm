from pymodbus.client import ModbusTcpClient
from modbus.modbus_client import ModbusClientBase
from models.device import Device

class TCPClient(ModbusClientBase):
    def __init__(self, device: Device):
        super().__init__(device)
        self.host = device.ip_address
        self.port = device.port or 502

    def connect(self) -> bool:
        if self.is_connected and self.client:
            return True

        self.client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=1.0
        )
        
        try:
            self.is_connected = self.client.connect()
            if self.is_connected:
                self.logger.info(f"Connected to TCP device '{self.device.name}' at {self.host}:{self.port}.")
            else:
                self.logger.warning(f"Failed to connect to TCP device '{self.device.name}' at {self.host}:{self.port}.")
            return self.is_connected
        except Exception as e:
            self.logger.error(f"Exception connecting to TCP device '{self.device.name}': {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        if self.client:
            self.client.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from TCP device '{self.device.name}'.")
