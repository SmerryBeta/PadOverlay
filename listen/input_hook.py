"""监听层：全局键鼠钩子，只听不拦截。"""
from __future__ import annotations

import sys
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

try:
    import keyboard
except ImportError:  # pragma: no cover
    keyboard = None

try:
    from pynput import mouse
except ImportError:  # pragma: no cover
    mouse = None

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
    _user32.GetCursorPos.restype = wintypes.BOOL
else:
    _POINT = None  # type: ignore
    _user32 = None

_MOUSE_NAMES = {
    "Button.left": "mouse_left",
    "Button.right": "mouse_right",
    "Button.middle": "mouse_middle",
}

# 相对位移多少 ≈ 右摇杆满偏；越小越灵敏
_RS_SENS = 2.5
# Raw 在近期有数据时，忽略光标差分，避免双计
_RAW_PRIORITY_S = 0.08


class InputHook:
    """
    键盘 + 鼠标监听。
    - 正常模式：按 keymap 回调 on_press / on_release（部件列表）
    - 录键模式：set_capture_callback 后，下一次按下调用回调(物理键名)并吞掉映射
    - 右摇杆鼠标源（可叠加，带去重）：
        1) Windows Raw Input 相对位移
        2) pynput 低级钩子坐标差分
        3) GetCursorPos 轮询（游戏自绘指针时 OS 光标仍可能在动）
    """

    def __init__(
        self,
        keymap: Dict[str, List[str]],
        on_press: Callable[[List[str]], None],
        on_release: Callable[[List[str]], None],
        on_rs_mouse: Optional[Callable[[Optional[float], Optional[float]], None]] = None,
    ) -> None:
        self._keymap = {k.lower(): list(v) for k, v in keymap.items()}
        self._on_press = on_press
        self._on_release = on_release
        self._on_rs_mouse = on_rs_mouse
        self._held_keys: Set[str] = set()
        self._kb_hook = None
        self._mouse_listener = None
        self._raw_mouse = None
        self._capture: Optional[Callable[[str], None]] = None
        self._last_mouse: Optional[Tuple[float, float]] = None
        self._raw_until = 0.0

    def set_keymap(self, keymap: Dict[str, List[str]]) -> None:
        held = list(self._held_keys)
        for name in held:
            parts = self._parts_for(name)
            self._held_keys.discard(name)
            if parts:
                self._on_release(parts)
        self._keymap = {k.lower(): list(v) for k, v in keymap.items()}

    def set_capture_callback(self, cb: Optional[Callable[[str], None]]) -> None:
        self._capture = cb

    def start(self, hwnd: Optional[int] = None) -> None:
        """
        hwnd: Windows 下用于注册 Raw Input 的窗口句柄（建议独立 sink，不要只用分层悬浮窗）。
        """
        if keyboard is not None:
            self._kb_hook = keyboard.hook(self._on_keyboard, suppress=False)

        if sys.platform == "win32" and self._on_rs_mouse is not None and hwnd:
            try:
                from listen.raw_mouse_win import RawMouseWin

                self._raw_mouse = RawMouseWin(self._on_raw_delta)
                if not self._raw_mouse.start(hwnd=int(hwnd)):
                    self._raw_mouse = None
            except Exception:
                self._raw_mouse = None

        if mouse is not None:
            # 始终听移动：全屏游戏里 Raw 经常丢，钩子/光标差分必须保留
            kwargs = {"on_click": self._on_mouse_click}
            if self._on_rs_mouse is not None:
                kwargs["on_move"] = self._on_mouse_move
            self._mouse_listener = mouse.Listener(**kwargs)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()

        # 初始光标，供 poll 差分
        self._last_mouse = self._read_cursor()

    def stop(self) -> None:
        if self._on_rs_mouse is not None:
            self._on_rs_mouse(None, None)
        self._last_mouse = None
        if self._raw_mouse is not None:
            try:
                self._raw_mouse.stop()
            except Exception:
                pass
            self._raw_mouse = None
        if keyboard is not None and self._kb_hook is not None:
            try:
                keyboard.unhook(self._kb_hook)
            except Exception:
                try:
                    keyboard.unhook_all()
                except Exception:
                    pass
            self._kb_hook = None
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

    def poll_cursor(self) -> None:
        """由悬浮窗定时器调用：轮询 OS 光标位置差分。"""
        if self._on_rs_mouse is None:
            return
        if time.perf_counter() < self._raw_until:
            # Raw 活跃时只同步坐标，不重复推摇杆
            pos = self._read_cursor()
            if pos is not None:
                self._last_mouse = pos
            return
        pos = self._read_cursor()
        if pos is None:
            return
        if self._last_mouse is None:
            self._last_mouse = pos
            return
        dx = pos[0] - self._last_mouse[0]
        dy = pos[1] - self._last_mouse[1]
        self._last_mouse = pos
        if dx == 0.0 and dy == 0.0:
            return
        self._emit_rs(dx, dy)

    def _read_cursor(self) -> Optional[Tuple[float, float]]:
        if _user32 is None or _POINT is None:
            return None
        pt = _POINT()
        if not _user32.GetCursorPos(ctypes.byref(pt)):
            return None
        return float(pt.x), float(pt.y)

    def _parts_for(self, name: str) -> List[str]:
        return list(self._keymap.get(name.lower(), []))

    def _emit_rs(self, dx: float, dy: float) -> None:
        if self._on_rs_mouse is None:
            return
        if dx == 0.0 and dy == 0.0:
            return
        sens = max(_RS_SENS, 1.0)
        nx = max(-1.0, min(1.0, dx / sens))
        ny = max(-1.0, min(1.0, dy / sens))
        self._on_rs_mouse(nx, ny)

    def _on_raw_delta(self, dx: int, dy: int) -> None:
        self._raw_until = time.perf_counter() + _RAW_PRIORITY_S
        self._emit_rs(float(dx), float(dy))

    def _emit_press(self, name: str) -> None:
        name = name.lower()
        if self._capture is not None:
            cb = self._capture
            self._capture = None
            cb(name)
            return
        if name in self._held_keys:
            return
        parts = self._parts_for(name)
        if not parts:
            return
        self._held_keys.add(name)
        self._on_press(parts)

    def _emit_release(self, name: str) -> None:
        name = name.lower()
        if name not in self._held_keys:
            return
        parts = self._parts_for(name)
        self._held_keys.discard(name)
        if parts:
            self._on_release(parts)

    def _on_keyboard(self, event) -> None:
        name = getattr(event, "name", None)
        if not name:
            return
        name = str(name).lower()
        et = getattr(event, "event_type", "")
        if et == "down":
            self._emit_press(name)
        elif et == "up":
            self._emit_release(name)

    def _on_mouse_click(self, _x, _y, button, pressed) -> None:
        name = _MOUSE_NAMES.get(str(button))
        if not name:
            return
        if pressed:
            self._emit_press(name)
        else:
            self._emit_release(name)

    def _on_mouse_move(self, x, y) -> None:
        fx, fy = float(x), float(y)
        if time.perf_counter() < self._raw_until:
            self._last_mouse = (fx, fy)
            return
        if self._last_mouse is None:
            self._last_mouse = (fx, fy)
            return
        dx = fx - self._last_mouse[0]
        dy = fy - self._last_mouse[1]
        self._last_mouse = (fx, fy)
        self._emit_rs(dx, dy)
