from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from typing import List

class ModbusParser:
    @staticmethod
    def parse(registers: List[int], data_type: str, byteorder=Endian.BIG, wordorder=Endian.BIG) -> float:
        """
        Parse raw registers into numerical value based on data type.
        """
        if not registers:
            return 0.0

        data_type = data_type.lower()
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=byteorder, wordorder=wordorder)
        
        try:
            val = 0
            if data_type == 'int16':
                val = decoder.decode_16bit_int()
            elif data_type == 'uint16':
                val = decoder.decode_16bit_uint()
            elif data_type == 'int32':
                val = decoder.decode_32bit_int()
            elif data_type == 'uint32':
                val = decoder.decode_32bit_uint()
            elif data_type == 'float32':
                val = decoder.decode_32bit_float()
            else:
                raise ValueError(f"Unknown data type: {data_type}")
                
            return float(val)
        except Exception as e:
            # Handle decode errors (e.g. not enough registers)
            raise ValueError(f"Failed to parse registers {registers} as {data_type}: {e}")

    @staticmethod
    def get_register_count(data_type: str) -> int:
        """Returns the number of 16-bit registers required for a data type."""
        data_type = data_type.lower()
        if data_type in ['int16', 'uint16']:
            return 1
        elif data_type in ['int32', 'uint32', 'float32']:
            return 2
        return 1
