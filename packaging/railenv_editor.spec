# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the RailEnv Editor.

Build with:  pyinstaller packaging/railenv_editor.spec
```

The PySide6 Qt plugin deployment is handled automatically by PyInstaller's
PySide6 hook. Add ``--windowed`` is implicit via ``console=False``.
"""

from PyInstaller.utils.hooks import collect_data_files

hiddenimports = ["numpy"]

a = Analysis(
    ["railenv_editor/app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="railenv-editor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="railenv-editor",
)

app = BUNDLE(
    coll,
    name="RailEnv Editor.app",
    icon=None,
    bundle_identifier="com.railenv.editor",
)
