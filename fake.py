from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSparseDataBlock
import threading
import time
import random

# -----------------------------
# Create Holding Registers
# 0 = 40001 → Gas
# 1 = 40002 → Temperature
# 2 = 40003 → Pressure
# -----------------------------
store = ModbusSlaveContext(
    hr=ModbusSparseDataBlock({
        0: 25,     # Gas
        1: 45,     # Temperature
        2: 1000    # Pressure
    })
)

context = ModbusServerContext(slaves=store, single=True)


# -----------------------------
# Background thread to update data
# -----------------------------
def update_values():
    while True:
        # Generate realistic changing values
        gas = random.randint(20, 30)
        temp = random.randint(40, 50)
        pressure = random.randint(990, 1050)

        # Function code 3 = Holding Registers
        store.setValues(3, 0, [gas, temp, pressure])

        print(f"Updated → Gas:{gas} Temp:{temp} Pressure:{pressure}")

        time.sleep(2)  # update every 2 seconds


# Start background updater thread
thread = threading.Thread(target=update_values, daemon=True)
thread.start()


# -----------------------------
# Start Modbus TCP Server
# -----------------------------
print("Modbus Fake Server Running on port 5020...")
StartTcpServer(context, address=("0.0.0.0", 5022))