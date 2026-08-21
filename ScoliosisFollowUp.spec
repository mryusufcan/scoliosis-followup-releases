# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/yusuf/Desktop/Scoliosis Follow Up/VERSION', '.'), ('C:/Users/yusuf/Desktop/Scoliosis Follow Up/resources/branding/logo.png', '.'), ('C:/Users/yusuf/Desktop/Scoliosis Follow Up/resources', 'resources')]
binaries = []
hiddenimports = ['license_app', 'cv2']
hiddenimports += collect_submodules('modular_app')
hiddenimports += collect_submodules('pacs')
hiddenimports += collect_submodules('dicom')
hiddenimports += collect_submodules('anonymization')
hiddenimports += collect_submodules('ai')
tmp_ret = collect_all('pylibjpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('libjpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openjpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rle')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('jpeg_ls')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:/Users/yusuf/Desktop/Scoliosis Follow Up/main.py'],
    pathex=['C:/Users/yusuf/Desktop/Scoliosis Follow Up'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ScoliosisFollowUp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/yusuf/Desktop/Scoliosis Follow Up/resources/branding/ScoliosisFollowUp.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ScoliosisFollowUp',
)
