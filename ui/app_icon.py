"""应用图标：托盘 / 任务栏 / 窗口 / 打包 exe 共用。"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QWidget

from app_paths import BUNDLE, ROOT

_ICON_REL = Path("assets") / "padoverlay.ico"
_APP_USER_MODEL_ID = "PadOverlay.App.1"


def icon_path() -> Path | None:
    for base in (ROOT, BUNDLE):
        p = base / _ICON_REL
        if p.is_file():
            return p
    return None


def make_app_icon() -> QIcon:
    """优先用 assets/padoverlay.ico，否则代码绘制同款。"""
    path = icon_path()
    if path is not None:
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return _paint_app_icon()


def make_tray_icon() -> QIcon:
    return make_app_icon()


def _paint_app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = size / 64.0
        p.setBrush(QColor(40, 44, 52))
        p.setPen(QColor(0, 220, 200))
        p.drawRoundedRect(
            int(6 * s), int(18 * s), int(52 * s), int(32 * s), int(12 * s), int(12 * s)
        )
        p.setBrush(QColor(0, 220, 200))
        p.drawEllipse(int(16 * s), int(28 * s), int(10 * s), int(10 * s))
        p.drawEllipse(int(38 * s), int(28 * s), int(10 * s), int(10 * s))
        p.end()
        icon.addPixmap(pm)
    return icon


def configure_windows_app_id() -> None:
    """必须在创建 QApplication 之前调用，否则任务栏会跟 python.exe 绑在一起。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception:
        pass


def apply_native_window_icon(widget: QWidget, icon: QIcon | None = None) -> None:
    """Qt setWindowIcon + Win32 WM_SETICON，确保任务栏按钮也换图标。"""
    ic = icon or make_app_icon()
    widget.setWindowIcon(ic)
    if sys.platform != "win32":
        return
    path = icon_path()
    if path is None:
        return
    try:
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        hwnd = int(widget.winId())
        if not hwnd:
            return
        path_str = str(path.resolve())
        h_small = user32.LoadImageW(None, path_str, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        h_big = user32.LoadImageW(None, path_str, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if h_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
        if h_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
    except Exception:
        pass
