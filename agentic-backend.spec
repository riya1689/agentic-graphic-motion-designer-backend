# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('packages')
hiddenimports += collect_submodules('sqlcipher3')
hiddenimports += ['win32cred', 'win32timezone', 'pywintypes', 'pythoncom']
hiddenimports += ['google_auth_oauthlib', 'google.oauth2.credentials', 'google.auth.transport.requests']
# `packages.icon_library` is a regular package, but its asset directory is not
# a Python package. Include the catalog explicitly so the frozen sidecar can
# seed the first-run SQLite database.
datas = [
    ('packages/icon_library/assets/builtin', 'packages/icon_library/assets/builtin'),
]
binaries = collect_dynamic_libs('sqlcipher3')


a = Analysis(
    ['desktop/sidecar/backend_launcher.py'],
    pathex=['.'],
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
    a.binaries,
    a.datas,
    [],
    name='agentic-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
