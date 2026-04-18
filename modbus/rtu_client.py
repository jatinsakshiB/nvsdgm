from pymodbus.client import ModbusSerialClient
from modbus.modbus_client import ModbusClientBase
from models.device import Device

class RTUClient(ModbusClientBase):
    def __init__(self, device: Device):
        super().__init__(device)
        self.port = device.com_port
        self.baudrate = device.baud_rate or 9600
        self.parity = device.parity or 'N'
        self.stopbits = device.stop_bits or 1

    def connect(self) -> bool:
        if self.is_connected and self.client:
            return True

        # Use multiple attempts to handle busy/releasing ports smoothly
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                self.client = ModbusSerialClient(
                    port=self.port,
                    baudrate=self.baudrate,
                    parity=self.parity,
                    stopbits=self.stopbits,
                    timeout=1.0
                )
                
                self.is_connected = self.client.connect()
                if self.is_connected:
                    self.logger.info(f"Connected to RTU device '{self.device.name}' on {self.port}.")
                    # Stabilization delay
                    import time
                    time.sleep(0.2)
                    return True
                
                if attempt < max_attempts - 1:
                    import time
                    time.sleep(0.3) # Wait before retry
                    
            except Exception as e:
                self.logger.warning(f"Connection attempt {attempt+1} failed for '{self.device.name}': {e}")
                if attempt == max_attempts - 1:
                    self.is_connected = False
                    return False
        
        self.logger.warning(f"Failed to connect to RTU device '{self.device.name}' after {max_attempts} attempts.")
        self.is_connected = False
        return False

    def disconnect(self):
        if self.client:
            self.client.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from RTU device '{self.device.name}'.")
