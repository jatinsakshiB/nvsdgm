import sqlite3
import os
import datetime
from typing import List, Optional, Tuple
from models.device import Device
from models.register import Register

class SQLiteManager:
    def __init__(self, db_path: str = "gas_analyzer.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database with required tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Devices Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    is_enabled BOOLEAN DEFAULT 1,
                    com_port TEXT,
                    baud_rate INTEGER,
                    parity TEXT,
                    stop_bits INTEGER,
                    ip_address TEXT,
                    port INTEGER,
                )
            ''')
            
            # Add new columns if they don't exist
            try:
                cursor.execute('ALTER TABLE devices ADD COLUMN byte_order TEXT DEFAULT "BIG"')
            except sqlite3.OperationalError:
                pass # Column exists
                
            try:
                cursor.execute('ALTER TABLE devices ADD COLUMN word_order TEXT DEFAULT "BIG"')
            except sqlite3.OperationalError:
                pass # Column exists
            
            # Registers Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS registers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    address INTEGER NOT NULL,
                    function_code INTEGER NOT NULL,
                    data_type TEXT NOT NULL,
                    scaling_factor REAL DEFAULT 1.0,
                    unit TEXT,
                    category TEXT,
                    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
                )
            ''')
            
            # History Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    device_id INTEGER NOT NULL,
                    register_id INTEGER NOT NULL,
                    value REAL NOT NULL,
                    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE,
                    FOREIGN KEY (register_id) REFERENCES registers (id) ON DELETE CASCADE
                )
            ''')
            
            # Logs Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source TEXT
                )
            ''')
            
            conn.commit()

    # --- Device CRUD ---
    def add_device(self, device: Device) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO devices (name, connection_type, is_enabled, com_port, baud_rate, parity, stop_bits, ip_address, port, slave_id, byte_order, word_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (device.name, device.connection_type, device.is_enabled, device.com_port, device.baud_rate, device.parity, device.stop_bits, device.ip_address, device.port, device.slave_id, device.byte_order, device.word_order))
            conn.commit()
            return cursor.lastrowid

    def update_device(self, device: Device):
        if device.id is None:
            raise ValueError("Device ID is required for update.")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE devices SET 
                    name=?, connection_type=?, is_enabled=?, com_port=?, baud_rate=?, parity=?, stop_bits=?, ip_address=?, port=?, slave_id=?, byte_order=?, word_order=?
                WHERE id=?
            ''', (device.name, device.connection_type, device.is_enabled, device.com_port, device.baud_rate, device.parity, device.stop_bits, device.ip_address, device.port, device.slave_id, device.byte_order, device.word_order, device.id))
            conn.commit()

    def get_devices(self) -> List[Device]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM devices')
            rows = cursor.fetchall()
            return [Device(
                id=row['id'], name=row['name'], connection_type=row['connection_type'], is_enabled=bool(row['is_enabled']),
                com_port=row['com_port'], baud_rate=row['baud_rate'], parity=row['parity'], stop_bits=row['stop_bits'],
                ip_address=row['ip_address'], port=row['port'], slave_id=row['slave_id'],
                byte_order=row.get('byte_order', 'BIG'), word_order=row.get('word_order', 'BIG')
            ) for row in rows]
            
    def delete_device(self, device_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deletes cascade to registers and history
            cursor.execute('PRAGMA foreign_keys = ON')
            cursor.execute('DELETE FROM devices WHERE id=?', (device_id,))
            conn.commit()

    # --- Register CRUD ---
    def add_register(self, register: Register) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO registers (device_id, name, address, function_code, data_type, scaling_factor, unit, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (register.device_id, register.name, register.address, register.function_code, register.data_type, register.scaling_factor, register.unit, register.category))
            conn.commit()
            return cursor.lastrowid

    def update_register(self, register: Register):
        if register.id is None:
            raise ValueError("Register ID is required for update.")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE registers SET 
                    device_id=?, name=?, address=?, function_code=?, data_type=?, scaling_factor=?, unit=?, category=?
                WHERE id=?
            ''', (register.device_id, register.name, register.address, register.function_code, register.data_type, register.scaling_factor, register.unit, register.category, register.id))
            conn.commit()

    def get_registers(self, device_id: Optional[int] = None) -> List[Register]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if device_id is not None:
                cursor.execute('SELECT * FROM registers WHERE device_id=?', (device_id,))
            else:
                cursor.execute('SELECT * FROM registers')
            rows = cursor.fetchall()
            return [Register(
                id=row['id'], device_id=row['device_id'], name=row['name'], address=row['address'],
                function_code=row['function_code'], data_type=row['data_type'], scaling_factor=row['scaling_factor'],
                unit=row['unit'], category=row['category']
            ) for row in rows]
            
    def delete_register(self, register_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM registers WHERE id=?', (register_id,))
            conn.commit()

    # --- History ---
    def add_history(self, device_id: int, register_id: int, value: float):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO history (device_id, register_id, value)
                VALUES (?, ?, ?)
            ''', (device_id, register_id, value))
            conn.commit()
            
    def get_history(self, device_id: int, register_id: int, limit: int = 1000) -> List[Tuple[str, float]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, value FROM history 
                WHERE device_id=? AND register_id=?
                ORDER BY timestamp DESC LIMIT ?
            ''', (device_id, register_id, limit))
            rows = cursor.fetchall()
            # Return ascending order for charts
            return [(row['timestamp'], row['value']) for row in reversed(rows)]

    # --- Logs ---
    def add_log(self, level: str, message: str, source: str = ""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO logs (level, message, source)
                VALUES (?, ?, ?)
            ''', (level, message, source))
            conn.commit()

    def get_logs(self, limit: int = 100) -> List[Tuple[str, str, str, str]]:
        """Returns list of (timestamp, level, message, source)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT timestamp, level, message, source FROM logs ORDER BY timestamp DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            return [(row['timestamp'], row['level'], row['message'], row['source']) for row in rows]
