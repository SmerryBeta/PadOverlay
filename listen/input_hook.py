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
_RS_SENS = 3.2
# 小于此像素/raw 单位的抖动直接丢掉
_RS_DEADZONE = 1.0
# 多路输入互斥：近期有更高优先级源时，低优先级只同步坐标不推摇杆
_RAW_PRIORITY_S = 0.10
_HOOK_PRIORITY_S = 0.06


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
        self._hook_until = 0.0

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
        """释放钩子；可能阻塞，调用方宜放后台线程并加超时。"""
        self._stop_qt_side()
        self._stop_hooks()

    def _stop_qt_side(self) -> None:
        """Raw Input / 回调：须在 Qt 主线程调用。"""
        if self._on_rs_mouse is not None:
            try:
                self._on_rs_mouse(None, None)
            except Exception:
                pass
        self._last_mouse = None
        raw = self._raw_mouse
        self._raw_mouse = None
        if raw is not None:
            try:
                raw.stop()
            except Exception:
                pass

    def _stop_hooks(self) -> None:
        """keyboard / pynput：可能卡很久，宜放后台。"""
        kb = self._kb_hook
        self._kb_hook = None
        if keyboard is not None and kb is not None:
            try:
                keyboard.unhook(kb)
            except Exception:
                try:
                    keyboard.unhook_all()
                except Exception:
                    pass
        listener = self._mouse_listener
        self._mouse_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def stop_async(self, timeout: float = 1.0) -> None:
        """主线程先卸 Qt 侧，钩子在守护线程卸，避免卡死 / 跨线程碰 Qt。

        调用方应先藏窗再调本方法：等卸钩时用户已看不到窗口。
        timeout<=0：只启动后台卸钩并立即返回；>0 则最多等 timeout 秒。
        """
        import threading

        self._stop_qt_side()
        done = threading.Event()

        def _run() -> None:
            try:
                self._stop_hooks()
            finally:
                done.set()

        threading.Thread(target=_run, name="hook-stop", daemon=True).start()
        if timeout > 0:
            done.wait(timeout=timeout)

    def poll_cursor(self) -> None:
        """由悬浮窗定时器调用：仅在钩子/Raw 静默时作兜底，避免与钩子双计导致抖动。"""
        if self._on_rs_mouse is None:
            return
        now = time.perf_counter()
        pos = self._read_cursor()
        if pos is None:
            return
        # Raw / 钩子活跃：只对齐坐标，不推摇杆
        if now < self._raw_until or now < self._hook_until:
            self._last_mouse = pos
            return
        if self._last_mouse is None:
            self._last_mouse = pos
            return
        dx = pos[0] - self._last_mouse[0]
        dy = pos[1] - self._last_mouse[1]
        self._last_mouse = pos
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
        if abs(dx) < _RS_DEADZONE and abs(dy) < _RS_DEADZONE:
            return
        # 死区内分量清零，避免单轴噪声拉抖
        if abs(dx) < _RS_DEADZONE:
            dx = 0.0
        if abs(dy) < _RS_DEADZONE:
            dy = 0.0
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
        self._hook_until = time.perf_counter() + _HOOK_PRIORITY_S
        self._emit_rs(dx, dy)
