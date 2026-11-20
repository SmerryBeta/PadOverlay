"""Windows Raw Input：相对鼠标位移（游戏锁光标也能收到）。

挂在 Qt 主线程窗口上（QAbstractNativeEventFilter），不要用独立线程消息泵。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable, Optional

from PyQt5.QtCore import QAbstractNativeEventFilter, QByteArray

user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RIDEV_EXINPUTSINK = 0x00001000
RIDEV_REMOVE = 0x00000001
MOUSE_MOVE_ABSOLUTE = 0x01


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", ctypes.c_void_p),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class _RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
    ]


class _RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("buttons", _RAWMOUSE_BUTTONS),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("u", _RAWMOUSE_UNION),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    wintypes.UINT,
    wintypes.UINT,
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.GetRawInputData.argtypes = [
    ctypes.c_void_p,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT,
]
user32.GetRawInputData.restype = wintypes.UINT


def _parse_delta(lparam: int) -> Optional[tuple]:
    size = wintypes.UINT(0)
    header_size = ctypes.sizeof(RAWINPUTHEADER)
    handle = ctypes.c_void_p(lparam)
    user32.GetRawInputData(handle, RID_INPUT, None, ctypes.byref(size), header_size)
    if size.value == 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    got = user32.GetRawInputData(
        handle, RID_INPUT, buf, ctypes.byref(size), header_size
    )
    if got == 0xFFFFFFFF or got == 0:
        return None
    raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
    if raw.header.dwType != RIM_TYPEMOUSE:
        return None
    if raw.mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
        return None
    dx = int(raw.mouse.lLastX)
    dy = int(raw.mouse.lLastY)
    if dx == 0 and dy == 0:
        return None
    return dx, dy


class RawMouseFilter(QAbstractNativeEventFilter):
    """拦截 WM_INPUT，回调相对位移。"""

    def __init__(self, on_delta: Callable[[int, int], None]) -> None:
        super().__init__()
        self._on_delta = on_delta

    def nativeEventFilter(self, eventType, message):  # noqa: N802
        # PyQt5.15：必须返回 (bool, result)，不能只返回 bool，否则每个系统消息都 TypeError 卡死
        et = bytes(eventType) if isinstance(eventType, QByteArray) else eventType
        if et not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
        except (TypeError, ValueError, ctypes.ArgumentError):
            return False, 0
        if msg.message != WM_INPUT:
            return False, 0
        delta = _parse_delta(int(msg.lParam))
        if delta is not None:
            try:
                self._on_delta(delta[0], delta[1])
            except Exception:
                pass
        return False, 0


class RawMouseWin:
    """
    在已有 Qt 窗口 hwnd 上注册 Raw Input，并安装 nativeEventFilter。
    """

    def __init__(self, on_delta: Callable[[int, int], None]) -> None:
        self._on_delta = on_delta
        self._filter: Optional[RawMouseFilter] = None
        self._hwnd: Optional[int] = None
        self._app = None

    def start(self, hwnd: Optional[int] = None) -> bool:
        if sys.platform != "win32":
            return False
        if self._filter is not None:
            return True
        if not hwnd:
            return False

        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01
        rid.usUsage = 0x02
        rid.dwFlags = RIDEV_INPUTSINK | RIDEV_EXINPUTSINK
        rid.hwndTarget = ctypes.c_void_p(int(hwnd))
        if not user32.RegisterRawInputDevices(
            ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
        ):
            rid.dwFlags = RIDEV_INPUTSINK
            if not user32.RegisterRawInputDevices(
                ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
            ):
                return False

        self._hwnd = int(hwnd)
        self._filter = RawMouseFilter(self._on_delta)
        self._app = app
        app.installNativeEventFilter(self._filter)
        return True

    def stop(self) -> None:
        if self._filter is not None and self._app is not None:
            try:
                self._app.removeNativeEventFilter(self._filter)
            except Exception:
                pass
        self._filter = None
        self._app = None
        if self._hwnd:
            try:
                rid = RAWINPUTDEVICE()
                rid.usUsagePage = 0x01
                rid.usUsage = 0x02
                rid.dwFlags = RIDEV_REMOVE
                rid.hwndTarget = None
                user32.RegisterRawInputDevices(
                    ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
                )
            except Exception:
                pass
        self._hwnd = None
