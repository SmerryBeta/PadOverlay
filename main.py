"""
PadOverlay — 键盘/鼠标 → 手柄按键高亮（仅可视化）

三层：listen（监听） / mapping（映射） / display（显示）
托盘控制：显示隐藏、映射设置、锁定拖动、退出（无全局软件热键）

运行：
    python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证以脚本方式运行时可 import 包
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from display.overlay import OverlayWindow
from listen.input_hook import InputHook
from mapping.mapper import KeyMapper
from mapping.pad_state import PadState
from ui.settings import SettingsWindow
from ui.tray import AppTray


class App:
    def __init__(self, qt: QApplication) -> None:
        self.qt = qt
        self.mapper = KeyMapper()
        self.state = PadState()
        self.overlay = OverlayWindow(self.state)
        # 位置/缩放由 config/window.yml 恢复
        self.overlay.settings_requested.connect(self.open_settings)
        self.overlay.close_requested.connect(self.quit)
        self.overlay.show()
        self.overlay.apply_saved_position()

        # 独立 Raw Input 接收窗（分层透明 Tool 窗在全屏游戏下经常收不到 WM_INPUT）
        self._raw_sink = QWidget()
        self._raw_sink.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        )
        self._raw_sink.setAttribute(Qt.WA_DontShowOnScreen, True)
        self._raw_sink.resize(1, 1)
        self._raw_sink.show()  # 必须 create 出 HWND
        raw_hwnd = int(self._raw_sink.winId())

        self.hook = InputHook(
            keymap=self.mapper.snapshot(),
            on_press=self.state.press,
            on_release=self.state.release,
            on_rs_mouse=self.state.set_rs_mouse,
        )
        self.hook.start(hwnd=raw_hwnd)
        self.overlay.set_mouse_poll(self.hook.poll_cursor)

        self._settings: SettingsWindow | None = None
        self._overlay_visible = True

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "PadOverlay", "系统托盘不可用，无法启动。")
            raise SystemExit(1)

        self.tray = AppTray(
            on_toggle_overlay=self.toggle_overlay,
            on_open_settings=self.open_settings,
            on_toggle_drag_lock=self.set_drag_lock,
            on_quit=self.quit,
            overlay_visible=True,
            drag_locked=False,
        )
        self.tray.show()
        qt.setQuitOnLastWindowClosed(False)
        qt.aboutToQuit.connect(self._cleanup)

    def toggle_overlay(self) -> None:
        if self._overlay_visible:
            self.hide_overlay()
        else:
            self.show_overlay()

    def show_overlay(self) -> None:
        self._overlay_visible = True
        self.overlay.show()
        self.tray.set_overlay_visible(True)

    def hide_overlay(self) -> None:
        self._overlay_visible = False
        self.overlay.hide()
        self.tray.set_overlay_visible(False)

    def set_drag_lock(self, locked: bool) -> None:
        self.overlay.set_drag_enabled(not locked)

    def open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsWindow(
                mapper=self.mapper,
                begin_capture=self._begin_capture,
                cancel_capture=self._cancel_capture,
            )
            self._settings.mappings_saved.connect(self._on_mappings_saved)
            self._settings.layout_saved.connect(self.overlay.reload_layout)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _begin_capture(self, cb) -> None:
        self.hook.set_capture_callback(cb)

    def _cancel_capture(self) -> None:
        self.hook.set_capture_callback(None)

    def _on_mappings_saved(self) -> None:
        self.state.clear()
        self.hook.set_keymap(self.mapper.snapshot())

    def quit(self) -> None:
        self._cleanup()
        self.qt.quit()

    def _cleanup(self) -> None:
        try:
            self.overlay._persist_now()
        except Exception:
            pass
        try:
            self.hook.stop()
        except Exception:
            pass
        try:
            self._raw_sink.hide()
            self._raw_sink.deleteLater()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass


def main() -> int:
    qt = QApplication(sys.argv)
    qt.setApplicationName("PadOverlay")
    App(qt)
    return qt.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
