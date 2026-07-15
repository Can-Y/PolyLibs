# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PolyLibs GUI."""

a = Analysis(
    ['polylibs_gui.py'],
    pathex=['PolyLibs'],
    binaries=[],
    datas=[
        ('FPGAer_Zone_258.jpg', '.'),
    ],
    hiddenimports=[
        'polylibs.generators.pads',
        'polylibs.generators.cadence',
        'polylibs.generators.altium',
        'polylibs.generators.kicad',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'yaml',
    ],
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
    name='PolyLibs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)



