from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QLineEdit, 
    QComboBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Signal
from database.sqlite_manager import SQLiteManager
from models.register import Register
import pandas as pd

class RegisterDialog(QDialog):
    def __init__(self, db: SQLiteManager, register: Register = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register Configuration")
        self.setMinimumWidth(400)
        self.db = db
        self.register = register
        
        layout = QFormLayout(self)
        
        self.device_combo = QComboBox()
        self.devices = self.db.get_devices()
        for d in self.devices:
            self.device_combo.addItem(f"{d.name} (ID: {d.id})", userData=d.id)
            
        self.name_input = QLineEdit()
        self.address_input = QLineEdit("0")
        
        self.func_combo = QComboBox()
        self.func_combo.addItems(["3 (Holding)", "4 (Input)"])
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["int16", "uint16", "int32", "uint32", "float32"])
        
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(["Gas", "Temperature", "Pressure", "Flow"])
        
        self.scale_input = QLineEdit("1.0")
        self.unit_input = QLineEdit()
        
        layout.addRow("Device:", self.device_combo)
        layout.addRow("Name:", self.name_input)
        layout.addRow("Address (0-based):", self.address_input)
        layout.addRow("Function Code:", self.func_combo)
        layout.addRow("Data Type:", self.type_combo)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Scaling Factor:", self.scale_input)
        layout.addRow("Unit:", self.unit_input)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)
        
        if self.register:
            self.load_register()

    def load_register(self):
        index = self.device_combo.findData(self.register.device_id)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)
            
        self.name_input.setText(self.register.name)
        self.address_input.setText(str(self.register.address))
        if self.register.function_code == 3:
            self.func_combo.setCurrentIndex(0)
        else:
            self.func_combo.setCurrentIndex(1)
            
        self.type_combo.setCurrentText(self.register.data_type)
        self.category_combo.setCurrentText(self.register.category)
        self.scale_input.setText(str(self.register.scaling_factor))
        self.unit_input.setText(self.register.unit)

    def get_register(self) -> Register:
        dev_id = self.device_combo.currentData()
        func_code = 3 if self.func_combo.currentIndex() == 0 else 4
        
        return Register(
            device_id=dev_id,
            name=self.name_input.text(),
            address=int(self.address_input.text() or 0),
            function_code=func_code,
            data_type=self.type_combo.currentText(),
            scaling_factor=float(self.scale_input.text() or 1.0),
            unit=self.unit_input.text(),
            category=self.category_combo.currentText(),
            id=self.register.id if self.register else None
        )

class RegisterManagerWidget(QWidget):
    registers_changed = Signal()

    def __init__(self, db: SQLiteManager, parent=None):
        super().__init__(parent)
        self.db = db
        
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Register")
        add_btn.clicked.connect(self.on_add)
        edit_btn = QPushButton("Edit Register")
        edit_btn.clicked.connect(self.on_edit)
        del_btn = QPushButton("Delete Register")
        del_btn.clicked.connect(self.on_delete)
        import_btn = QPushButton("Import Excel")
        import_btn.clicked.connect(self.on_import)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_data)
        
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(del_btn)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Device ID", "Name", "Address", "FC", "Type", "Scale", "Unit"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        regs = self.db.get_registers()
        self.table.setRowCount(0)
        for r in regs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.id)))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.device_id)))
            self.table.setItem(row, 2, QTableWidgetItem(r.name))
            self.table.setItem(row, 3, QTableWidgetItem(str(r.address)))
            self.table.setItem(row, 4, QTableWidgetItem(str(r.function_code)))
            self.table.setItem(row, 5, QTableWidgetItem(r.data_type))
            self.table.setItem(row, 6, QTableWidgetItem(str(r.scaling_factor)))
            self.table.setItem(row, 7, QTableWidgetItem(r.unit))

    def on_add(self):
        devices = self.db.get_devices()
        if not devices:
            QMessageBox.warning(self, "Warning", "Please add a device first.")
            return

        dialog = RegisterDialog(db=self.db, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                new_reg = dialog.get_register()
                new_reg.validate()
                self.db.add_register(new_reg)
                self.load_data()
                self.registers_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def on_edit(self):
        sel = self.table.selectedItems()
        if not sel: return
        reg_id = int(self.table.item(sel[0].row(), 0).text())
        
        regs = self.db.get_registers()
        reg = next((r for r in regs if r.id == reg_id), None)
        if not reg: return
        
        dialog = RegisterDialog(db=self.db, register=reg, parent=self)
        if dialog.exec() == QDialog.Accepted:
            try:
                updated_reg = dialog.get_register()
                updated_reg.validate()
                self.db.update_register(updated_reg)
                self.load_data()
                self.registers_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def on_delete(self):
        sel = self.table.selectedItems()
        if not sel: return
        reg_id = int(self.table.item(sel[0].row(), 0).text())
        
        reply = QMessageBox.question(self, "Delete", f"Are you sure you want to delete Register ID {reg_id}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_register(reg_id)
            self.load_data()
            self.registers_changed.emit()

    def on_import(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if not file: return
        
        try:
            df = pd.read_excel(file)
            required = ['device_id', 'name', 'address', 'function_code', 'data_type']
            for req in required:
                if req not in df.columns:
                    raise ValueError(f"Missing required column: {req}")
                    
            for _, row in df.iterrows():
                scale = row.get('scaling_factor', 1.0)
                unit = str(row.get('unit', ''))
                if pd.isna(scale): scale = 1.0
                if unit == 'nan': unit = ''
                
                cat = str(row.get('category', 'Gas'))
                if cat == 'nan': cat = 'Gas'

                reg = Register(
                    device_id=int(row['device_id']),
                    name=str(row['name']),
                    address=int(row['address']),
                    function_code=int(row['function_code']),
                    data_type=str(row['data_type']),
                    scaling_factor=float(scale),
                    unit=unit,
                    category=cat
                )
                reg.validate()
                self.db.add_register(reg)
                
            QMessageBox.information(self, "Success", "Registers imported successfully.")
            self.load_data()
            self.registers_changed.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")
