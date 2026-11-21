"""
PadOverlay — 键盘/鼠标 → 手柄按键高亮（仅可视化）

三层：listen（监听） / mapping（映射） / display（显示）
托盘控制：显示隐藏、映射设置、锁定拖动、退出（无全局软件热键）

运行：
    python main.py

控制台 Ctrl+C 可退出。
"""
from __future__ import annotations

import signal
import sys
from pathlib import Path

# 保证以脚本方式运行时可 import 包
_BOOT = Path(__file__).resolve().parent
if str(_BOOT) not in sys.path:
    sys.path.insert(0, str(_BOOT))

from app_paths import ROOT, ensure_sidecar_assets

# 打包 exe：旁路没有 config/skins 时先从内嵌资源拷出
ensure_sidecar_assets()

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from display.overlay import OverlayWindow
from listen.input_hook import InputHook
from mapping.mapper import KeyMapper
from mapping.pad_state import PadState
from ui.app_icon import apply_native_window_icon, configure_windows_app_id, make_app_icon
from ui.settings import SettingsWindow
from ui.tray import AppTray


class App:
    def __init__(self, qt: QApplication) -> None:
        self.qt = qt
        self._quitting = False
        self._cleaned = False
        self.mapper = KeyMapper()
        self.state = PadState()
        self.overlay = OverlayWindow(self.state)
        # 位置/缩放由 config/window.yml 恢复
        self.overlay.settings_requested.connect(self.open_settings)
        self.overlay.close_requested.connect(self.quit)
        self.overlay.show()
        self.overlay.apply_saved_position()
        # show 之后 HWND 才就绪，再打一次 WM_SETICON 给任务栏
        apply_native_window_icon(self.overlay)

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
        apply_native_window_icon(self._settings)

    def _begin_capture(self, cb) -> None:
        self.hook.set_capture_callback(cb)

    def _cancel_capture(self) -> None:
        self.hook.set_capture_callback(None)

    def _on_mappings_saved(self) -> None:
        self.state.clear()
        self.hook.set_keymap(self.mapper.snapshot())

    def quit(self) -> None:
        """✕ / 托盘 / Ctrl+C：先秒关窗口，再后台卸钩子结束事件循环。"""
        if self._quitting:
            return
        self._quitting = True
        try:
            self.overlay.close_requested.disconnect(self.quit)
        except Exception:
            pass
        # 先停轮询，避免退出过程中还在摸钩子
        try:
            self.overlay.set_mouse_poll(None)
        except Exception:
            pass
        # 立刻藏窗/托盘，卸钩子可能要几百毫秒～数秒，不能挡在视觉关闭前面
        try:
            self.overlay.hide()
        except Exception:
            pass
        try:
            if self._settings is not None:
                self._settings.hide()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        QTimer.singleShot(0, self._finish_quit)

    def _finish_quit(self) -> None:
        self._cleanup()
        self.qt.quit()

    def _cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        try:
            self.overlay._persist_now()
        except Exception:
            pass
        # 窗口已藏，这里等卸钩不影响观感；仍限时，防 keyboard/pynput 卡死退出
        try:
            self.hook.stop_async(timeout=1.0)
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
    # 先于 QApplication：否则任务栏仍显示 python.exe 图标
    configure_windows_app_id()

    qt = QApplication(sys.argv)
    qt.setApplicationName("PadOverlay")
    # 与托盘同一套图标 → 任务栏 / Alt+Tab / 直播姬窗口列表
    qt.setWindowIcon(make_app_icon())

    # Qt 事件循环里要定期回到 Python，Ctrl+C 的 signal 才能被处理
    _sig_pump = QTimer()
    _sig_pump.setInterval(200)
    _sig_pump.timeout.connect(lambda: None)
    _sig_pump.start()

    app = App(qt)

    def _on_sigint(*_args) -> None:
        print("\n[PadOverlay] Ctrl+C，退出中…", flush=True)
        QTimer.singleShot(0, app.quit)

    signal.signal(signal.SIGINT, _on_sigint)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _on_sigint)

    return qt.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
