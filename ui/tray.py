"""系统托盘：显示/隐藏、设置、锁定拖动、退出。"""
from __future__ import annotations

from typing import Callable

from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon


def make_tray_icon() -> QIcon:
    """生成简易手柄风格托盘图标（无外部资源）。"""
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(40, 44, 52))
    p.setPen(QColor(0, 220, 200))
    p.drawRoundedRect(6, 18, 52, 32, 12, 12)
    p.setBrush(QColor(0, 220, 200))
    p.drawEllipse(16, 28, 10, 10)
    p.drawEllipse(38, 28, 10, 10)
    p.end()
    return QIcon(pm)


class AppTray:
    def __init__(
        self,
        *,
        on_toggle_overlay: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_toggle_drag_lock: Callable[[bool], None],
        on_quit: Callable[[], None],
        overlay_visible: bool = True,
        drag_locked: bool = False,
    ) -> None:
        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip("PadOverlay")

        menu = QMenu()
        self.act_show = QAction("隐藏悬浮窗" if overlay_visible else "显示悬浮窗")
        self.act_show.triggered.connect(on_toggle_overlay)
        menu.addAction(self.act_show)

        act_settings = QAction("映射设置…")
        act_settings.triggered.connect(on_open_settings)
        menu.addAction(act_settings)

        self.act_lock = QAction("锁定拖动")
        self.act_lock.setCheckable(True)
        self.act_lock.setChecked(drag_locked)
        self.act_lock.toggled.connect(on_toggle_drag_lock)
        menu.addAction(self.act_lock)

        menu.addSeparator()
        act_quit = QAction("退出")
        act_quit.triggered.connect(on_quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self._on_open_settings = on_open_settings
        self._on_toggle_overlay = on_toggle_overlay

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            # 左键单击：打开设置
            self._on_open_settings()
        elif reason == QSystemTrayIcon.DoubleClick:
            self._on_toggle_overlay()

    def set_overlay_visible(self, visible: bool) -> None:
        self.act_show.setText("隐藏悬浮窗" if visible else "显示悬浮窗")

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()
