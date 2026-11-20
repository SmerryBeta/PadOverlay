# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller：单文件 PadOverlay.exe，内嵌 config + skins。"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "config"), "config"),
    (str(ROOT / "skins"), "skins"),
    (str(ROOT / "assets"), "assets"),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "yaml",
        "keyboard",
        "pynput",
        "pynput.keyboard",
        "pynput.mouse",
        "pynput._util.win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tools",
        "smoke_test",
        "tkinter",
        "matplotlib",
        "numpy",
        "pygame",
    ],
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
    name="PadOverlay",
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
    # 与托盘绘制同款：任务栏 / 资源管理器里的 exe 图标
    icon=str(ROOT / "assets" / "padoverlay.ico"),
)
