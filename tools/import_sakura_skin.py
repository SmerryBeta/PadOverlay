"""从樱花主题拼图裁切 skins/sakura_pad（只裁切，不变形）。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt5.QtGui import QImage, qAlpha, qBlue, qGreen, qRed, qRgba
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "skins" / "sakura_pad"
# 默认用皮肤目录内 org.png；也可: python tools/import_sakura_skin.py <拼图路径>
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "org.png"
# 布局参考 neon_pad 画布
REF_W, REF_H = 447, 293

Box = Tuple[int, int, int, int]

INACTIVE: Dict[str, Box] = {
    "btn_a": (480, 63, 535, 119),
    "btn_b": (547, 63, 605, 119),
    "btn_x": (617, 63, 673, 119),
    "btn_y": (684, 63, 742, 119),
    "lt": (774, 42, 861, 118),
    "rt": (896, 42, 981, 118),
    "lb": (489, 157, 595, 199),
    "rb": (618, 157, 723, 199),
    "btn_view": (752, 161, 814, 198),
    "btn_menu": (841, 161, 905, 198),
    "ls": (491, 238, 564, 310),
    "rs": (577, 238, 650, 310),
    "dpad": (665, 239, 746, 313),
    "dpad_up": (927, 213, 970, 253),
    "dpad_down": (927, 298, 970, 338),
    "dpad_left": (887, 254, 929, 297),
    "dpad_right": (968, 254, 1011, 297),
}

ACTIVE: Dict[str, Box] = {
    "btn_a": (480, 404, 537, 461),
    "btn_b": (549, 405, 606, 460),
    "btn_x": (618, 405, 674, 461),
    "btn_y": (685, 405, 742, 461),
    "lt": (774, 383, 862, 459),
    "rt": (896, 383, 981, 459),
    "lb": (490, 497, 596, 540),
    "rb": (615, 497, 718, 539),
    "btn_view": (750, 501, 812, 539),
    "btn_menu": (840, 501, 905, 539),
    "ls": (486, 576, 562, 650),
    "rs": (577, 576, 653, 650),
    "dpad": (668, 579, 752, 654),
    "dpad_up": (926, 542, 968, 584),
    "dpad_down": (926, 637, 968, 677),
    "dpad_left": (884, 593, 925, 636),
    "dpad_right": (966, 592, 1009, 636),
}

BASE_BOX: Box = (13, 39, 489, 337)

# neon_pad 已调布局（位置参考）
REF = {
    "base_x": 54.0,
    "base_y": 58.0,
    "base_scale": 0.751,
    "base_rot": 0.0,
    "lt": (113.0, 4.0, 0.683),
    "rt": (276.0, 4.0, 0.683),
    "lb": (54.0, 52.0, 0.624),
    "rb": (334.0, 54.0, 0.621),
    "btn_y": (311.0, 102.0, 0.515),
    "btn_x": (289.0, 122.0, 0.514),
    "btn_b": (332.0, 123.0, 0.514),
    "btn_a": (310.0, 142.0, 0.468),
    "btn_view": (197.0, 121.0, 0.351),
    "btn_menu": (247.0, 120.0, 0.351),
    "guide": (223.0, 105.0, 1.0),
    "ls": (136.0, 122.0, 0.751),
    "rs": (266.0, 172.0, 0.751),
    "dpad": (178.0, 173.0, 0.683),
}


def clean_alpha(img: QImage) -> QImage:
    src = img.convertToFormat(QImage.Format_ARGB32)
    w, h = src.width(), src.height()
    out = QImage(w, h, QImage.Format_ARGB32)
    out.fill(0)
    for y in range(h):
        for x in range(w):
            c = src.pixel(x, y)
            a = qAlpha(c)
            if a == 0:
                continue
            out.setPixel(x, y, qRgba(qRed(c), qGreen(c), qBlue(c), a))
    return out


def alpha_bbox(img: QImage, *, thr: int = 1, pad: int = 0) -> Optional[Box]:
    w, h = img.width(), img.height()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if qAlpha(img.pixel(x, y)) > thr:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if maxx < 0:
        return None
    return (
        max(0, minx - pad),
        max(0, miny - pad),
        min(w - 1, maxx + pad),
        min(h - 1, maxy + pad),
    )


def crop(img: QImage, box: Box) -> QImage:
    x0, y0, x1, y1 = box
    return img.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def pad_box(box: Box, pad: int, w: int, h: int) -> Box:
    x0, y0, x1, y1 = box
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(w - 1, x1 + pad),
        min(h - 1, y1 + pad),
    )


def save_png(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise RuntimeError(f"save failed {path}")


def export_part(raw: QImage, box: Box, path: Path) -> Tuple[int, int]:
    piece = clean_alpha(crop(raw, box))
    tight = alpha_bbox(piece, thr=1, pad=0)
    if tight:
        piece = crop(piece, tight)
    save_png(piece, path)
    return piece.width(), piece.height()


def write_meta(base_w: int, base_h: int, sizes: Dict[str, Tuple[int, int]]) -> None:
    sx, sy = base_w / REF_W, base_h / REF_H

    def mx(x: float) -> float:
        return round(x * sx, 1)

    def my(y: float) -> float:
        return round(y * sy, 1)

    lines = [
        "# sakura_pad — 樱花主题。位置参考 neon_pad，按画布比例映射。",
        "# bumper w/h = 本套裁切原图像素。布置布局可再微调。",
        "",
        "canvas:",
        f"  w: {base_w}",
        f"  h: {base_h}",
        f"  base_x: {mx(REF['base_x'])}",
        f"  base_y: {my(REF['base_y'])}",
        f"  base_scale: {REF['base_scale']}",
        f"  base_rot: {REF['base_rot']}",
        "",
        "parts:",
    ]

    for name in ("lt", "rt", "lb", "rb"):
        x, y, sc = REF[name]
        bw, bh = sizes[name]
        lines.append(
            f"  {name}:\n"
            f"    type: bumper\n"
            f"    x: {mx(x)}\n"
            f"    y: {my(y)}\n"
            f"    w: {bw}\n"
            f"    h: {bh}\n"
            f"    label: {name.upper()}\n"
            f"    scale: {sc}"
        )

    for name, lab in (
        ("btn_y", "Y"),
        ("btn_x", "X"),
        ("btn_b", "B"),
        ("btn_a", "A"),
    ):
        x, y, sc = REF[name]
        r = max(8, sizes[name][0] // 2)
        lines.append(
            f"  {name}:\n"
            f"    type: face\n"
            f"    x: {mx(x)}\n"
            f"    y: {my(y)}\n"
            f"    r: {r}\n"
            f"    label: {lab}\n"
            f"    scale: {sc}"
        )

    for name in ("btn_view", "btn_menu"):
        x, y, sc = REF[name]
        r = max(6, sizes[name][0] // 2)
        lines.append(
            f"  {name}:\n"
            f"    type: small\n"
            f"    x: {mx(x)}\n"
            f"    y: {my(y)}\n"
            f"    r: {r}\n"
            f"    scale: {sc}"
        )

    gx, gy, _ = REF["guide"]
    lines.append(
        f"  guide:\n"
        f"    type: guide\n"
        f"    x: {mx(gx)}\n"
        f"    y: {my(gy)}\n"
        f"    r: 10"
    )

    for name in ("ls", "rs"):
        x, y, sc = REF[name]
        r = max(12, sizes[name][0] // 2)
        lines.append(
            f"  {name}:\n"
            f"    type: stick\n"
            f"    x: {mx(x)}\n"
            f"    y: {my(y)}\n"
            f"    r: {r}\n"
            f"    scale: {sc}"
        )

    dx, dy, sc = REF["dpad"]
    arm = max(12, sizes["dpad"][0] // 2)
    lines.append(
        f"  dpad:\n"
        f"    type: dpad\n"
        f"    x: {mx(dx)}\n"
        f"    y: {my(dy)}\n"
        f"    arm: {arm}\n"
        f"    scale: {sc}"
    )

    (OUT / "layout.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "skin.yml").write_text(
        "name: 樱花 Sakura\n"
        "mode: image\n"
        "base: base.png\n"
        "active_dir: active\n"
        "inactive_dir: inactive\n",
        encoding="utf-8",
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    raw = QImage(str(SRC)).convertToFormat(QImage.Format_ARGB32)
    if raw.isNull():
        print("bad", SRC)
        return 1
    w, h = raw.width(), raw.height()
    print("src", SRC, f"{w}x{h}")

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, OUT / "_source_sheet.png")

    base = clean_alpha(crop(raw, BASE_BOX))
    tb = alpha_bbox(base, thr=8, pad=1)
    if tb:
        base = crop(base, tb)
    save_png(base, OUT / "base.png")
    print("base", base.width(), base.height())

    sizes: Dict[str, Tuple[int, int]] = {}
    for name in INACTIVE:
        ib = pad_box(INACTIVE[name], 1, w, h)
        ab = pad_box(ACTIVE[name], 1, w, h)
        iw, ih = export_part(raw, ib, OUT / "inactive" / f"{name}.png")
        aw, ah = export_part(raw, ab, OUT / "active" / f"{name}.png")
        sizes[name] = (iw, ih)
        print(f"  {name}: {iw}x{ih} / active {aw}x{ah}")

    write_meta(base.width(), base.height(), sizes)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
