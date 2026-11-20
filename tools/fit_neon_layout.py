"""根据 neon_pad/base.png 开孔，估一版 layout.yml 锚点。"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PyQt5.QtGui import QImage, qAlpha
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "skins" / "neon_pad" / "base.png"
LAYOUT = ROOT / "skins" / "neon_pad" / "layout.yml"


def flood(img: QImage, sx: int, sy: int, visited):
    w, h = img.width(), img.height()
    if visited[sy][sx] or qAlpha(img.pixel(sx, sy)) > 20:
        return None
    q = deque([(sx, sy)])
    visited[sy][sx] = True
    minx = maxx = sx
    miny = maxy = sy
    area = 0
    while q:
        x, y = q.popleft()
        area += 1
        minx, maxx = min(minx, x), max(maxx, x)
        miny, maxy = min(miny, y), max(maxy, y)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            if visited[ny][nx]:
                continue
            if qAlpha(img.pixel(nx, ny)) > 20:
                continue
            visited[ny][nx] = True
            q.append((nx, ny))
    return (minx, miny, maxx, maxy, area)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    img = QImage(str(BASE))
    w, h = img.width(), img.height()
    visited = [[False] * w for _ in range(h)]
    holes = []
    for y in range(h):
        for x in range(w):
            if visited[y][x]:
                continue
            if qAlpha(img.pixel(x, y)) > 20:
                visited[y][x] = True
                continue
            box = flood(img, x, y, visited)
            if not box:
                continue
            area = box[4]
            bw = box[2] - box[0] + 1
            bh = box[3] - box[1] + 1
            if area < 80 or area > 8000:
                continue
            if bw < 10 or bh < 10:
                continue
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            holes.append((cx, cy, bw, bh, area, box))

    holes.sort(key=lambda t: (t[1], t[0]))
    print(f"base {w}x{h} holes={len(holes)}")
    for t in holes:
        print(f"  c=({t[0]:.0f},{t[1]:.0f}) size={t[2]}x{t[3]} area={t[4]}")

    # 启发式命名：按位置匹配 Xbox 布局
    def nearest(targets, pred):
        cands = [t for t in holes if pred(t)]
        return cands

    # 右侧面键：x 较大、接近圆形
    face = [t for t in holes if t[0] > w * 0.55 and 18 < t[2] < 55 and 18 < t[3] < 55]
    face.sort(key=lambda t: t[1])
    # 通常 Y 最上，然后 X/B，A 最下
    named = {}
    if len(face) >= 4:
        face_sorted = sorted(face, key=lambda t: (t[1], t[0]))
        # diamond: top=Y, left=X, right=B, bottom=A
        top = min(face, key=lambda t: t[1])
        bot = max(face, key=lambda t: t[1])
        mid = [t for t in face if t not in (top, bot)]
        mid.sort(key=lambda t: t[0])
        named["btn_y"] = top
        named["btn_a"] = bot
        if len(mid) >= 2:
            named["btn_x"] = mid[0]
            named["btn_b"] = mid[1]

    sticks = [t for t in holes if 40 < t[2] < 100 and 40 < t[3] < 100 and abs(t[2] - t[3]) < 15]
    sticks.sort(key=lambda t: t[0])
    if len(sticks) >= 2:
        # 左上 ls，右下 rs
        sticks.sort(key=lambda t: (t[1], t[0]))
        leftish = sorted(sticks, key=lambda t: t[0])
        named["ls"] = min(sticks, key=lambda t: t[0] + t[1] * 0.2)
        named["rs"] = max(sticks, key=lambda t: t[0] + t[1] * 0.3)

    # dpad：偏左下、略十字（较大）
    dpad_cands = [
        t
        for t in holes
        if t[0] < w * 0.45 and t[1] > h * 0.5 and t[2] > 35 and t[3] > 35
    ]
    if dpad_cands:
        named["dpad"] = max(dpad_cands, key=lambda t: t[4])

    small = [t for t in holes if 12 < t[2] < 35 and 12 < t[3] < 35 and t[0] > w * 0.35]
    small.sort(key=lambda t: t[0])
    if len(small) >= 2:
        named["btn_view"] = small[0]
        named["btn_menu"] = small[1] if len(small) > 1 else small[0]

    guide = [t for t in holes if 25 < t[2] < 55 and abs(t[0] - w / 2) < 40 and abs(t[1] - h * 0.45) < 60]
    if guide:
        named["guide"] = min(guide, key=lambda t: abs(t[0] - w / 2))

    # bumpers：顶部扁长透明/暗区不一定是洞；用壳体顶部估算
    # 若没检测到，保留比例默认
    print("named", {k: (round(v[0]), round(v[1]), v[2], v[3]) for k, v in named.items()})

    def r_of(t):
        return max(6, int(min(t[2], t[3]) / 2))

    parts = {
        "lt": f"{{type: bumper, x: {int(w*0.28)}, y: {int(h*0.06)}, w: {int(w*0.14)}, h: {int(h*0.07)}, label: LT}}",
        "rt": f"{{type: bumper, x: {int(w*0.58)}, y: {int(h*0.06)}, w: {int(w*0.14)}, h: {int(h*0.07)}, label: RT}}",
        "lb": f"{{type: bumper, x: {int(w*0.28)}, y: {int(h*0.14)}, w: {int(w*0.14)}, h: {int(h*0.055)}, label: LB}}",
        "rb": f"{{type: bumper, x: {int(w*0.58)}, y: {int(h*0.14)}, w: {int(w*0.14)}, h: {int(h*0.055)}, label: RB}}",
    }
    for key, typ in (
        ("btn_y", "face"),
        ("btn_x", "face"),
        ("btn_b", "face"),
        ("btn_a", "face"),
        ("btn_view", "small"),
        ("btn_menu", "small"),
        ("guide", "guide"),
        ("ls", "stick"),
        ("rs", "stick"),
    ):
        if key not in named:
            continue
        t = named[key]
        extra = ""
        if key.startswith("btn_") and key[-1] in "abxy":
            extra = f", label: {key[-1].upper()}"
        parts[key] = (
            f"{{type: {typ}, x: {int(t[0])}, y: {int(t[1])}, r: {r_of(t)}{extra}}}"
        )
    if "dpad" in named:
        t = named["dpad"]
        arm = max(10, int(max(t[2], t[3]) / 2))
        parts["dpad"] = f"{{type: dpad, x: {int(t[0])}, y: {int(t[1])}, arm: {arm}}}"

    lines = [
        f"# neon_pad — 由 base 开孔拟合 ({w}x{h})",
        "",
        "canvas:",
        f"  w: {w}",
        f"  h: {h}",
        "",
        "parts:",
    ]
    order = [
        "lt",
        "rt",
        "lb",
        "rb",
        "btn_y",
        "btn_x",
        "btn_b",
        "btn_a",
        "btn_view",
        "btn_menu",
        "guide",
        "ls",
        "rs",
        "dpad",
    ]
    for k in order:
        if k in parts:
            lines.append(f"  {k}: {parts[k]}")
    LAYOUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", LAYOUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
