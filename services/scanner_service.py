import socket
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from models.device import Device

try:
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

@dataclass
class ScanResult:
    ip: str = ""
    port_name: str = "" # For RTU
    baud_rate: int = 0   # For RTU
    is_online: bool = False  # Ping or TCP success
    port_open: bool = False  # Port 502 open or COM accessible
    is_modbus: bool = False  # Valid Modbus response
    response_time: float = 0.0
    status_msg: str = "Offline"
    logs: List[str] = field(default_factory=list)

    def add_log(self, msg: str):
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

class ScannerService:
    def __init__(self, port: int = 502, timeout: float = 1.0):
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger("ScannerService")
        self._stop_requested = False

    def get_local_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def get_subnet(self, ip: str) -> str:
        parts = ip.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:-1])
        return "192.168.1"

    def list_com_ports(self) -> List[Dict[str, str]]:
        """List all available serial ports."""
        if not HAS_SERIAL:
            return []
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                "device": p.device,
                "description": p.description,
                "hwid": p.hwid
            })
        return ports

    async def scan_subnet(self, subnet: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[ScanResult]:
        self._stop_requested = False
        results = []
        tasks = []
        
        # Scan 1 to 254
        total = 254
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            tasks.append(self.scan_ip(ip))

        # Run in chunks to avoid OS limits on open descriptors
        chunk_size = 50
        for i in range(0, len(tasks), chunk_size):
            if self._stop_requested:
                break
            chunk = tasks[i:i + chunk_size]
            chunk_results = await asyncio.gather(*chunk)
            results.extend(chunk_results)
            if progress_callback:
                progress_callback(len(results), total)

        return results

    def stop(self):
        self._stop_requested = True

    async def scan_ip(self, ip: str) -> ScanResult:
        result = ScanResult(ip=ip)
        start_time = time.time()
        
        try:
            # 1. Port Check (Async)
            result.add_log(f"Checking port {self.port} on {ip}...")
            conn = asyncio.open_connection(ip, self.port)
            try:
                reader, writer = await asyncio.wait_for(conn, timeout=self.timeout)
                writer.close()
                await writer.wait_closed()
                
                result.is_online = True
                result.port_open = True
                result.response_time = (time.time() - start_time) * 1000
                result.add_log(f"Port {self.port} is OPEN.")
                
                # 2. Modbus Handshake (Sync, run in executor)
                loop = asyncio.get_event_loop()
                is_modbus, msg = await loop.run_in_executor(None, self._check_modbus, ip)
                result.is_modbus = is_modbus
                result.status_msg = msg
                result.add_log(msg)
                
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                result.is_online = False
                result.port_open = False
                result.status_msg = "Offline / Port Closed"
                # result.add_log("Connection failed or timed out.")
                
        except Exception as e:
            result.add_log(f"Error scanning {ip}: {str(e)}")
            result.status_msg = "Error"

        return result

    def _check_modbus(self, ip: str) -> (bool, str):
        """Perform a real Modbus handshake. Returns (success, message)."""
        client = ModbusTcpClient(host=ip, port=self.port, timeout=self.timeout)
        try:
            if not client.connect():
                return False, "Failed to connect for handshake"
            
            # Try to read Unit ID 1, holding register 0
            # Most devices respond to this even if register doesn't exist (with error code)
            # or return valid data.
            res = client.read_holding_registers(address=0, count=1, slave=1)
            
            if res.isError():
                # Even if it's an error (like Illegal Data Address), 
                # if it's a Modbus Error response, it IS a Modbus device.
                # However, connection refused or timeout wouldn't get here.
                # If we get a response that pymodbus can parse as an error, it's a Modbus device.
                return True, "Modbus Device ✅ (Responded with Error code)"
            
            return True, "Modbus Device ✅"
            
        except Exception as e:
            return False, f"Handshake failed: {str(e)}"
        finally:
            client.close()

    def test_connection(self, ip: str, port: int) -> ScanResult:
        """Synchronous version for single IP diagnostic."""
        result = ScanResult(ip=ip)
        result.add_log(f"Starting diagnostic for {ip}:{port}")
        
        # Simple socket check first
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        start = time.time()
        try:
            sock.connect((ip, port))
            result.is_online = True
            result.port_open = True
            result.response_time = (time.time() - start) * 1000
            result.add_log(f"TCP Port {port} is OPEN. Time: {result.response_time:.2f}ms")
            sock.close()
            
            # Modbus check
            is_modbus, msg = self._check_modbus(ip)
            result.is_modbus = is_modbus
            result.status_msg = msg
            result.add_log(msg)
            
        except socket.timeout:
            result.status_msg = "Timeout ❌"
            result.add_log("Connection timed out.")
        except ConnectionRefusedError:
            result.status_msg = "Connection Refused ⚠️"
            result.add_log("Port is closed or unreachable.")
        except Exception as e:
            result.status_msg = f"Error: {str(e)}"
            result.add_log(f"Exception: {str(e)}")
        finally:
            sock.close()
            
        return result

    def scan_usb_port(self, port: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[ScanResult]:
        """Scan a single USB port across common baud rates."""
        common_bauds = [9600, 19200, 38400, 57600, 115200]
        results = []
        total = len(common_bauds)
        
        self._stop_requested = False
        for i, baud in enumerate(common_bauds):
            if self._stop_requested:
                break
                
            res = ScanResult(port_name=port, baud_rate=baud)
            res.add_log(f"Probing {port} at {baud} baud...")
            
            # Use short timeout for scanning
            client = ModbusSerialClient(
                port=port,
                baudrate=baud,
                timeout=0.5,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            
            start = time.time()
            try:
                if client.connect():
                    res.port_open = True
                    # Handshake
                    response = client.read_holding_registers(address=0, count=1, slave=1)
                    res.response_time = (time.time() - start) * 1000
                    
                    if not response.isError():
                        res.is_modbus = True
                        res.is_online = True
                        res.status_msg = "Modbus Device ✅"
                        res.add_log(f"Success! Found Modbus device at {baud} baud.")
                    else:
                        # Could be wrong baud or just no device at ID 1
                        res.status_msg = "Port Open, Handshake Failed"
                        res.add_log(f"Port opened at {baud} but Modbus check failed: {response}")
                    
                    client.close()
                else:
                    res.status_msg = "Could not open port"
            except Exception as e:
                res.status_msg = f"Error: {str(e)}"
            
            results.append(res)
            if progress_callback:
                progress_callback(i + 1, total)
                
        return results

    def discover_registers(self, client_params: Dict[str, Any], start: int = 0, count: int = 100, fc: int = 3, 
                           progress_callback: Optional[Callable[[int, int], None]] = None,
                           log_callback: Optional[Callable[[str], None]] = None,
                           global_logger: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Identify which registers are active in a given range."""
        found = []
        self._stop_requested = False
        slave = client_params.get("slave_id", 1)
        
        def _emit_log(msg, level="INFO"):
            if log_callback: log_callback(msg)
            if global_logger:
                if level == "INFO": global_logger.info(msg, "Discovery")
                elif level == "WARNING": global_logger.warning(msg, "Discovery")
                elif level == "ERROR": global_logger.error(msg, "Discovery")

        _emit_log(f"🚀 Starting POWER DISCOVERY: Start={start}, Count={count}, Slave={slave}")
        if fc == 0:
            _emit_log("🔍 Mode: AUTO-SCAN (Trying both Holding and Input registers)")
            
        # Emit initial progress IMMEDIATELY
        if progress_callback:
            progress_callback(0, count)

        # Use slightly longer timeout for discovery to be safe with long cables/USB
        timeout = 1.5

        if "ip_address" in client_params:
            host = client_params["ip_address"]
            port = client_params.get("port", 502)
            _emit_log(f"Preparing TCP connection to {host}:{port}...")
            client = ModbusTcpClient(host=host, port=port, timeout=timeout)
        else:
            p = client_params["port"]
            b = client_params["baud_rate"]
            _emit_log(f"Preparing USB/Serial port {p} at {b} baud (Timeout={timeout}s)...")
            client = ModbusSerialClient(
                port=p, 
                baudrate=b,
                timeout=timeout,
                parity=client_params.get("parity", 'N'),
                stopbits=client_params.get("stop_bits", 1),
                bytesize=8
            )

        try:
            _emit_log("📡 Attempting to connect to hardware...", "INFO")
            if not client.connect():
                _emit_log(f"❌ FAILED to connect. Check cable, port {client_params.get('ip_address') or client_params.get('port')}, and Slave ID.", "ERROR")
                return []

            _emit_log("✅ Connection SUCCESS. Scanning with inter-packet delay for stability...", "INFO")

            # Try address one by one
            for i in range(start, start + count):
                if self._stop_requested: break
                
                if progress_callback: progress_callback(i - start, count)
                
                # Try multiple function codes if in AUTO mode (fc=0)
                fcs_to_try = [3, 4] if fc == 0 else [fc]
                
                for current_fc in fcs_to_try:
                    fc_name = "Holding" if current_fc == 3 else "Input"
                    if log_callback: log_callback(f"Probing {fc_name} Addr {i}...")
                    
                    try:
                        # Give USB bus a moment to breathe
                        time.sleep(0.05) 
                        
                        if current_fc == 3:
                            res = client.read_holding_registers(address=i, count=1, slave=slave)
                        else:
                            res = client.read_input_registers(address=i, count=1, slave=slave)
                        
                        if not res.isError():
                            val = res.registers[0]
                            found.append({
                                "address": i,
                                "value": val,
                                "type": fc_name
                            })
                            _emit_log(f"✨ SUCCESS! Addr {i} ({fc_name}) = {val}")
                            # If we found it as one type, we usually don't need to probe the other 
                            # for the same address, unless specified. For discovery, one is enough.
                            break 
                        else:
                            if log_callback: log_callback(f"  └─ ❌ No data at {i} ({str(res)})")
                    except Exception as e:
                        if log_callback: log_callback(f"  └─ ⚠️ Timeout at {i}")
                    
                if progress_callback: progress_callback(i - start + 1, count)
            
            _emit_log(f"🏁 Discovery Finished. Found {len(found)} active addresses.")
        finally:
            client.close()
                
    def diagnostic_sweep(self, port: str, 
                         progress_callback: Optional[Callable[[int, int], None]] = None,
                         log_callback: Optional[Callable[[str], None]] = None,
                         global_logger: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """
        Deep scan of a serial port to find any Modbus device by trying all common
        baud rates, parities, and Slave IDs.
        """
        self._stop_requested = False
        common_bauds = [9600, 19200, 38400, 57600, 115200]
        common_parities = ['N', 'E', 'O']
        # Most devices use small IDs (1-10) or common ones like 100, 247, 255.
        common_slaves = [1, 2, 3, 4, 5, 10, 100, 247, 255]
        
        total_steps = len(common_bauds) * len(common_parities) * len(common_slaves)
        current_step = 0
        
        def _emit_log(msg, level="INFO"):
            if log_callback: log_callback(msg)
            if global_logger:
                if level == "INFO": global_logger.info(msg, "Diagnostic")
                elif level == "WARNING": global_logger.warning(msg, "Diagnostic")
                elif level == "ERROR": global_logger.error(msg, "Diagnostic")

        _emit_log(f"🕵️ Starting Deep Hardware Diagnostic on {port}...", "INFO")
        
        for baud in common_bauds:
            for parity in common_parities:
                if self._stop_requested: break
                
                _emit_log(f"🔎 Testing configuration: {baud} baud, Parity={parity}...")
                
                client = ModbusSerialClient(
                    port=port,
                    baudrate=baud,
                    parity=parity,
                    timeout=0.5, # Short timeout for sweep
                    stopbits=1,
                    bytesize=8
                )
                
                try:
                    if not client.connect():
                        _emit_log(f"❌ Failed to open port {port}. Is it in use?", "ERROR")
                        return None
                    
                    for slave in common_slaves:
                        if self._stop_requested: break
                        current_step += 1
                        if progress_callback: progress_callback(current_step, total_steps)
                        
                        if log_callback: log_callback(f"   Trying Slave ID {slave}...")
                        
                        # Try reading address 0 (Holding)
                        res = client.read_holding_registers(address=0, count=1, slave=slave)
                        if not res.isError():
                            _emit_log(f"🎉 FOUND DEVICE! Baud={baud}, Parity={parity}, Slave={slave}", "INFO")
                            client.close()
                            return {"baud": baud, "parity": parity, "slave": slave, "port": port}
                        
                        # Give adapter a tiny break
                        time.sleep(0.01)
                        
                    client.close()
                except Exception as e:
                    _emit_log(f"⚠️ Error on configs: {e}", "WARNING")
                finally:
                    client.close()
                    
        _emit_log("🏁 Deep Scan finished. No device found. Check wiring (A/B) and power.", "WARNING")
        return None
