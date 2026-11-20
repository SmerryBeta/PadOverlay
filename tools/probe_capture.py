"""模拟直播姬/OBS：枚举顶层窗 + BitBlt / PrintWindow 试抓 PadOverlay。"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0

GetWindowLong = user32.GetWindowLongW
GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
GetWindowLong.restype = ctypes.c_long


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _title(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _visible_for_streamer(hwnd: int) -> bool:
    """接近 OBS/直播姬窗口列表过滤：可见、有标题、非 ToolWindow（除非 APPWINDOW）。"""
    if not user32.IsWindowVisible(hwnd):
        return False
    title = _title(hwnd)
    if not title.strip():
        return False
    ex = GetWindowLong(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    if (ex & WS_EX_TOOLWINDOW) and not (ex & WS_EX_APPWINDOW):
        return False
    return True


def enum_streamer_windows() -> list[dict]:
    out: list[dict] = []

    def cb(hwnd, _lp):
        if not _visible_for_streamer(hwnd):
            return True
        l, t, r, b = _rect(hwnd)
        ex = GetWindowLong(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        out.append(
            {
                "hwnd": int(hwnd),
                "title": _title(hwnd),
                "class": _class(hwnd),
                "pid": _pid(hwnd),
                "w": r - l,
                "h": b - t,
                "exstyle": f"0x{ex:08X}",
                "layered": bool(ex & WS_EX_LAYERED),
                "tool": bool(ex & WS_EX_TOOLWINDOW),
                "app": bool(ex & WS_EX_APPWINDOW),
            }
        )
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def find_pad_candidates() -> list[dict]:
    """不按 Tool 过滤，专门找标题/类名像 PadOverlay 的窗。"""
    hits: list[dict] = []

    def cb(hwnd, _lp):
        title = _title(hwnd)
        cls = _class(hwnd)
        if "PadOverlay" not in title and "PadOverlay" not in cls:
            # Qt 无边框窗类名常是 Qt5QWindowIcon / Qt5152QWindowIcon 等，靠标题
            if title != "PadOverlay":
                return True
        l, t, r, b = _rect(hwnd)
        ex = GetWindowLong(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        hits.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "class": cls,
                "pid": _pid(hwnd),
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "w": r - l,
                "h": b - t,
                "exstyle": f"0x{ex:08X}",
                "layered": bool(ex & WS_EX_LAYERED),
                "tool": bool(ex & WS_EX_TOOLWINDOW),
                "app": bool(ex & WS_EX_APPWINDOW),
                "in_streamer_list": _visible_for_streamer(hwnd),
            }
        )
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return hits


def _grab(hwnd: int, method: str) -> tuple[bytes | None, int, int, str]:
    l, t, r, b = _rect(hwnd)
    w, h = r - l, b - t
    if w <= 0 or h <= 0:
        return None, 0, 0, "empty rect"

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    old = gdi32.SelectObject(hdc_mem, hbmp)

    ok = False
    note = method
    if method == "BitBlt":
        # 从屏幕 DC 裁剪（能采到已合成的分层窗，但会被遮挡影响）
        ok = bool(gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, l, t, SRCCOPY))
        note = "BitBlt(screen DC crop)"
    elif method == "BitBlt_window":
        hdc_win = user32.GetWindowDC(hwnd)
        ok = bool(gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, SRCCOPY))
        user32.ReleaseDC(hwnd, hdc_win)
        note = "BitBlt(window DC)"
    elif method == "PrintWindow":
        ok = bool(user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT))
        note = "PrintWindow(PW_RENDERFULLCONTENT)"
    else:
        note = "unknown method"

    pixels = None
    if ok:
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        buf = (ctypes.c_char * (w * h * 4))()
        got = gdi32.GetDIBits(hdc_screen, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        if got:
            pixels = bytes(buf)
        else:
            note += " | GetDIBits failed"
            ok = False
    else:
        note += " | blit/print failed"

    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)
    return pixels, w, h, note


def _stats(pixels: bytes, w: int, h: int) -> dict:
    # BGRA
    n = w * h
    black = 0
    nonzero = 0
    # sample + full scan for black ratio
    for i in range(0, len(pixels), 4):
        b, g, r, a = pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]
        if b | g | r:
            nonzero += 1
        else:
            black += 1
    return {
        "pixels": n,
        "nonzero_rgb": nonzero,
        "black_rgb": black,
        "black_ratio": round(black / n, 4) if n else 1.0,
        "likely_black_frame": (nonzero / n) < 0.01 if n else True,
    }


def _write_bmp(path: Path, pixels: bytes, w: int, h: int) -> None:
    # 32-bit BGRA top-down -> simple BMP
    row = w * 4
    # BMP wants bottom-up BGRX, 4-byte aligned (already)
    bottom_up = b"".join(pixels[i : i + row] for i in range((h - 1) * row, -1, -row))
    header = BITMAPINFOHEADER()
    header.biSize = 40
    header.biWidth = w
    header.biHeight = h
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    header.biSizeImage = len(bottom_up)
    file_size = 14 + 40 + len(bottom_up)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(b"BM")
        f.write(file_size.to_bytes(4, "little"))
        f.write((0).to_bytes(4, "little"))
        f.write((14 + 40).to_bytes(4, "little"))
        f.write(bytes(header))
        f.write(bottom_up)


def main() -> int:
    out_dir = Path(__file__).resolve().parents[1] / "tmp" / "capture_probe"
    print("=== PadOverlay candidates (any Tool/layered) ===")
    hits = find_pad_candidates()
    if not hits:
        print("NOT FOUND: no window titled PadOverlay")
        print("(Is the overlay running and visible?)")
        return 2
    for h in hits:
        print(h)

    print("\n=== In streamer-style EnumWindows list? ===")
    streamer = enum_streamer_windows()
    pad_in = [w for w in streamer if "PadOverlay" in w["title"]]
    if pad_in:
        print("YES — appears in list:")
        for w in pad_in:
            print(w)
    else:
        print("NO — filtered out (ToolWindow / invisible / empty title)")
        print(f"(streamer list has {len(streamer)} windows total)")

    # 优先：可见、非 Tool、尺寸像样的主悬浮窗（跳过 tooltip / raw sink）
    ranked = sorted(
        hits,
        key=lambda x: (
            0 if x.get("in_streamer_list") else 1,
            0 if x.get("visible") else 1,
            0 if not x.get("tool") else 1,
            -(x.get("w", 0) * x.get("h", 0)),
        ),
    )
    target = ranked[0]
    hwnd = target["hwnd"]
    print(f"\n=== Capture probe target={target} ===")
    print(f"=== Capture probe hwnd={hwnd} ===")
    for method in ("BitBlt", "BitBlt_window", "PrintWindow"):
        pixels, w, h, note = _grab(hwnd, method)
        if not pixels:
            print(f"{method}: FAIL — {note}")
            continue
        st = _stats(pixels, w, h)
        bmp = out_dir / f"{method}.bmp"
        _write_bmp(bmp, pixels, w, h)
        print(f"{method}: {note}")
        print(f"  size={w}x{h} stats={st} saved={bmp}")

    print(f"\nBitmaps -> {out_dir}")
    return 0 if pad_in else 1


if __name__ == "__main__":
    sys.exit(main())
