from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSparseDataBlock
import threading
import time
import random
import subprocess
import os

def free_port(port):
    """Checks if a port is in use and kills the process using it."""
    try:
        # Check if port is in use and get PIDs using lsof
        result = subprocess.check_output(["lsof", "-ti", f":{port}"], stderr=subprocess.STDOUT)
        pids = result.decode().strip().split('\n')
        for pid in pids:
            if pid:
                print(f"Port {port} is busy (PID: {pid}). Freeing up...")
                subprocess.run(["kill", "-9", pid])
                time.sleep(1) # Wait for port to clear
    except subprocess.CalledProcessError:
        # Port is not in use
        pass
    except Exception as e:
        print(f"Error checking port {port}: {e}")

# -----------------------------
# Create Holding Registers
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
PORT = 502
free_port(PORT)
print(f"Modbus Fake Server Running on port {PORT}...")
StartTcpServer(context, address=("0.0.0.0", PORT))