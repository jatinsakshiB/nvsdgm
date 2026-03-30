# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# List of folders to include in the bundle
# (Paths are relative to this spec file)
data_files = [
    ('ui', 'ui'),
    ('services', 'services'),
    ('modbus', 'modbus'),
    ('models', 'models'),
    ('database', 'database'),
]

a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=data_files,
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='NVSDGM',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False, # Set to True for debugging background processes
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon=None) # Add icon file path here e.g. 'icon.ico'

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='NVSDGM')
