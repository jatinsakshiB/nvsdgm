from dataclasses import dataclass
from typing import Optional

@dataclass
class Register:
    device_id: int
    name: str
    address: int
    function_code: int       # 3 for Holding, 4 for Input
    data_type: str           # 'int16', 'uint16', 'int32', 'uint32', 'float32'
    scaling_factor: float = 1.0
    unit: str = ""
    category: str = "Gas"    # e.g., Gas, Temperature, Pressure
    
    # DB ID
    id: Optional[int] = None

    def validate(self):
        if self.function_code not in (3, 4):
            raise ValueError(f"Unsupported function code: {self.function_code}")
        valid_types = ('int16', 'uint16', 'int32', 'uint32', 'float32')
        if self.data_type not in valid_types:
            raise ValueError(f"Unsupported data type '{self.data_type}'. Must be one of {valid_types}.")
