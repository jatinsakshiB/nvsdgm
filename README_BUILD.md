# NVSDGM - Build & Distribution Guide

This guide explains how to create a professional **.exe** and **Installer** for the NVSDGM application.

## Prerequisites

1. **Windows PC**: To create a Windows `.exe`, you must build it on a Windows machine.
2. **Python 3.9+**: Ensure Python is installed and added to your PATH.
3. **Inno Setup**: Download and install [Inno Setup](https://jrsoftware.org/isdl.php) (optional, for creating the installer).

---

## Step 1: Prepare the Environment

Open your terminal (CMD or PowerShell) in the project directory and run:

```powershell
# Create a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller
```

---

## Step 2: Build the Executable

We use **PyInstaller** with the provided `nvsdgm.spec` file. This ensures all folders (`ui`, `services`, etc.) are bundled correctly.

```powershell
pyinstaller --clean nvsdgm.spec
```

- **Output**: After the build finishes, you will find a `dist/NVSDGM` folder.
- **Test**: Run `dist/NVSDGM/NVSDGM.exe` to make sure it works.
  - *Note*: The database will automatically be created in `%APPDATA%\NVSDGM\gas_analyzer.db`.

---

## Step 3: Create a Professional Installer (Recommended)

To make it "properly" installable with a Desktop shortcut and Start Menu entry, use **Inno Setup**.

1. Open **Inno Setup Compiler**.
2. Select **File -> New** to start the Script Wizard.
3. **Application Information**:
   - Name: `NVSDGM`
   - Version: `1.0.0`
   - Publisher: `Your Name/Company`
4. **Application Files**:
   - **Main executable**: Select `dist\NVSDGM\NVSDGM.exe`.
   - **Add folder**: Click "Add folder" and select the entire `dist\NVSDGM` folder. When asked about subfolders, say **Yes**.
5. **Application Icons**:
   - Check "Create a desktop shortcut".
6. **Compile**:
   - Follow the rest of the wizard and click **Finish**.
   - It will generate an `Output\setup.exe` which is your final professional installer.

---

## Why this is "Proper"?

1. **Persistent Data**: I have updated `main.py` so the database is stored in `%APPDATA%`. This means if you update the app, your data isn't lost.
2. **Clean Bundle**: The `.spec` file handles all sub-packages automatically.
3. **Standard Installer**: Using Inno Setup provides the "Professional" feel users expect (Standard installation wizard, Add/Remove Programs support).

---

## Troubleshooting

- **Missing Modules**: If you add new folders to the project, remember to add them to the `data_files` list in `nvsdgm.spec`.
- **Icon**: If you have an `.ico` file, update the `icon=None` line in `nvsdgm.spec` to `icon='your_icon.ico'`.
