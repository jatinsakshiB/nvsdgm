from dataclasses import dataclass
from typing import Optional

@dataclass
class Device:
    name: str
    connection_type: str  # "RTU" or "TCP"
    is_enabled: bool = True
    
    # RTU specific
    com_port: Optional[str] = None
    baud_rate: Optional[int] = 9600
    parity: Optional[str] = 'N'
    stop_bits: Optional[int] = 1
    
    # TCP specific
    ip_address: Optional[str] = None
    port: Optional[int] = 502
    
    # Common
    slave_id: int = 1
    byte_order: str = 'BIG'  # 'BIG' or 'LITTLE'
    word_order: str = 'BIG'  # 'BIG' or 'LITTLE'
    
    # DB ID
    id: Optional[int] = None
    
    def validate(self):
        if self.connection_type not in ("RTU", "TCP"):
            raise ValueError(f"Invalid connection type: {self.connection_type}")
        if self.connection_type == "RTU" and not self.com_port:
            raise ValueError("COM port is required for RTU connections")
        if self.connection_type == "TCP" and not self.ip_address:
            raise ValueError("IP address is required for TCP connections")
