from abc import ABC, abstractmethod
from typing import List, Optional
from models.device import Device
import logging

class ModbusClientBase(ABC):
    def __init__(self, device: Device):
        self.device = device
        self.client = None
        self.is_connected = False
        self.logger = logging.getLogger("ModbusClient")

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the device."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the device."""
        pass

    def read_registers(self, address: int, count: int, function_code: int) -> Optional[List[int]]:
        """
        Read registers from the device.
        Returns a list of 16-bit integers, or None if failed.
        """
        if not self.client or not self.is_connected:
            self.logger.error(f"Cannot read, device {self.device.name} not connected.")
            return None

        try:
            slave = self.device.slave_id
            if function_code == 3:
                result = self.client.read_holding_registers(address=address, count=count, slave=slave)
            elif function_code == 4:
                result = self.client.read_input_registers(address=address, count=count, slave=slave)
            else:
                self.logger.error(f"Unsupported function code {function_code}.")
                return None

            if result.isError():
                self.logger.error(f"Modbus Error: Device '{self.device.name}' (Slave {slave}) failed to read address {address}. Error: {result}")
                return None

            return result.registers
        except Exception as e:
            self.logger.error(f"Timeout/Exception: Device '{self.device.name}' (Slave {slave}) failed at address {address}: {str(e)}")
            return None
