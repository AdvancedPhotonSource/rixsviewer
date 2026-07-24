# packaging/windows/rixsviewer.spec
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

spec_dir = Path(SPECPATH)
repo_root = spec_dir.parent.parent

a = Analysis(
    [str(spec_dir / 'entrypoint.py')],
    pathex=[],
    binaries=[],
    datas=[
        (str(repo_root / 'src' / 'rixsviewer' / 'assets'), 'rixsviewer/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['epics'],
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
    name='rixsviewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(spec_dir / 'icon.ico'),
)
