"""从猫纹主题拼图裁切 skins/calico_pad（只裁切，不变形）。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt5.QtGui import QImage, qAlpha, qBlue, qGreen, qRed, qRgba
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(
    r"C:\Users\30724\.cursor\projects\s-pyProjects-PadOverlay\assets"
    r"\____Xbox_______-e6668979-aa90-4478-b760-184edca2c991.png"
)
OUT = ROOT / "skins" / "calico_pad"

Box = Tuple[int, int, int, int]

INACTIVE: Dict[str, Box] = {
    "btn_a": (480, 63, 533, 117),
    "btn_b": (547, 63, 601, 116),
    "btn_x": (616, 64, 669, 116),
    "btn_y": (683, 64, 737, 117),
    "lt": (773, 43, 856, 119),
    "rt": (896, 43, 979, 119),
    "lb": (490, 157, 592, 198),
    "rb": (616, 157, 717, 196),
    "btn_view": (750, 161, 809, 199),
    "btn_menu": (840, 161, 903, 198),
    "ls": (488, 236, 559, 307),
    "rs": (575, 237, 645, 306),
    "dpad": (672, 238, 747, 310),
    "dpad_up": (922, 214, 963, 254),
    "dpad_down": (922, 295, 963, 335),
    "dpad_left": (879, 255, 920, 296),
    "dpad_right": (965, 255, 1005, 296),
}

ACTIVE: Dict[str, Box] = {
    "btn_a": (480, 398, 533, 455),
    "btn_b": (546, 398, 601, 455),
    "btn_x": (615, 398, 670, 454),
    "btn_y": (682, 398, 739, 455),
    "lt": (771, 379, 857, 457),
    "rt": (894, 379, 981, 457),
    "lb": (489, 490, 594, 533),
    "rb": (616, 490, 718, 532),
    "btn_view": (750, 495, 810, 535),
    "btn_menu": (840, 494, 903, 535),
    "ls": (485, 573, 557, 645),
    "rs": (575, 573, 646, 645),
    "dpad": (671, 574, 748, 649),
    "dpad_up": (922, 535, 964, 577),
    "dpad_down": (923, 619, 964, 661),
    "dpad_left": (879, 580, 920, 621),
    "dpad_right": (965, 580, 1006, 621),
}

BASE_BOX: Box = (16, 38, 479, 335)


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
    cw, ch = base_w, base_h

    def X(n: float) -> int:
        return int(n * cw)

    def Y(n: float) -> int:
        return int(n * ch)

    lines = [
        "# calico_pad — 猫纹主题。bumper 用图片原始 w/h。",
        "# 请在设置「布置布局」里拖到开孔对齐后保存。",
        "",
        "canvas:",
        f"  w: {cw}",
        f"  h: {ch}",
        "  base_x: 0.0",
        "  base_y: 0.0",
        "  base_scale: 1.0",
        "  base_rot: 0.0",
        "",
        "parts:",
    ]
    for name, (nx, ny) in (
        ("lt", (0.28, 0.05)),
        ("rt", (0.58, 0.05)),
        ("lb", (0.28, 0.13)),
        ("rb", (0.58, 0.13)),
    ):
        bw, bh = sizes[name]
        lines.append(
            f"  {name}: {{type: bumper, x: {X(nx)}, y: {Y(ny)}, w: {bw}, h: {bh}, label: {name.upper()}, scale: 0.65}}"
        )

    for name, (nx, ny, lab) in (
        ("btn_y", (0.80, 0.22, "Y")),
        ("btn_x", (0.73, 0.30, "X")),
        ("btn_b", (0.86, 0.30, "B")),
        ("btn_a", (0.80, 0.38, "A")),
    ):
        r = max(8, sizes[name][0] // 2)
        lines.append(
            f"  {name}: {{type: face, x: {X(nx)}, y: {Y(ny)}, r: {r}, label: {lab}, scale: 0.65}}"
        )

    for name, (nx, ny) in (("btn_view", (0.44, 0.30)), ("btn_menu", (0.56, 0.30))):
        r = max(6, sizes[name][0] // 2)
        lines.append(
            f"  {name}: {{type: small, x: {X(nx)}, y: {Y(ny)}, r: {r}, scale: 0.55}}"
        )

    lines.append(f"  guide: {{type: guide, x: {X(0.50)}, y: {Y(0.36)}, r: 10}}")

    for name, (nx, ny) in (("ls", (0.26, 0.30)), ("rs", (0.66, 0.52))):
        r = max(12, sizes[name][0] // 2)
        lines.append(
            f"  {name}: {{type: stick, x: {X(nx)}, y: {Y(ny)}, r: {r}, scale: 0.7}}"
        )

    arm = max(12, sizes["dpad"][0] // 2)
    lines.append(
        f"  dpad: {{type: dpad, x: {X(0.38)}, y: {Y(0.52)}, arm: {arm}, scale: 0.7}}"
    )

    (OUT / "layout.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "skin.yml").write_text(
        "name: 猫纹 Calico\n"
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
