"""从 PS 修好的拼图裁切 neon_pad：只裁切，不缩放/不变形 LT RT LB RB。"""
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
    r"\Xbox__________-fa569578-9d0b-495d-a644-e30f27dbfbea.png"
)
OUT = ROOT / "skins" / "neon_pad"

Box = Tuple[int, int, int, int]

# 实测 alpha 连通域（INACTIVE）；ACTIVE = 同框 y+341
INACTIVE: Dict[str, Box] = {
    "btn_a": (480, 64, 531, 113),
    "btn_b": (550, 65, 596, 112),
    "btn_x": (619, 65, 666, 113),
    "btn_y": (684, 65, 733, 113),
    "lt": (771, 42, 851, 117),
    "rt": (894, 42, 971, 117),
    "lb": (492, 157, 590, 196),
    "rb": (617, 157, 710, 192),
    "btn_view": (750, 162, 805, 196),
    "btn_menu": (839, 162, 895, 196),
    "ls": (490, 239, 555, 302),
    "rs": (578, 239, 643, 303),
    "dpad": (673, 241, 745, 309),
    "dpad_up": (922, 213, 961, 250),
    "dpad_down": (922, 297, 961, 334),
    "dpad_left": (880, 255, 917, 294),
    "dpad_right": (964, 255, 1000, 294),
}
ACTIVE_DY = 341


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


def alpha_bbox(
    img: QImage, *, thr: int = 1, pad: int = 1
) -> Optional[Box]:
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


def shift(box: Box, dy: int, h: int) -> Box:
    x0, y0, x1, y1 = box
    return (x0, max(0, y0 + dy), x1, min(h - 1, y1 + dy))


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
    """原图像素裁切，不缩放。"""
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
        "# neon_pad — PS 修图裁切。bumper 使用图片原始 w/h，避免拉伸。",
        "# 请在设置「布置布局」里拖到开孔对齐后保存。",
        "",
        "canvas:",
        f"  w: {cw}",
        f"  h: {ch}",
        "",
        "parts:",
    ]
    # LT/RT/LB/RB：原生尺寸
    for name, (nx, ny) in (
        ("lt", (0.28, 0.05)),
        ("rt", (0.58, 0.05)),
        ("lb", (0.28, 0.13)),
        ("rb", (0.58, 0.13)),
    ):
        bw, bh = sizes[name]
        lines.append(
            f"  {name}: {{type: bumper, x: {X(nx)}, y: {Y(ny)}, w: {bw}, h: {bh}, label: {name.upper()}}}"
        )

    for name, (nx, ny, lab) in (
        ("btn_y", (0.80, 0.22, "Y")),
        ("btn_x", (0.73, 0.30, "X")),
        ("btn_b", (0.86, 0.30, "B")),
        ("btn_a", (0.80, 0.38, "A")),
    ):
        r = max(8, sizes[name][0] // 2)
        lines.append(
            f"  {name}: {{type: face, x: {X(nx)}, y: {Y(ny)}, r: {r}, label: {lab}}}"
        )

    for name, (nx, ny) in (("btn_view", (0.44, 0.30)), ("btn_menu", (0.56, 0.30))):
        r = max(6, sizes[name][0] // 2)
        lines.append(f"  {name}: {{type: small, x: {X(nx)}, y: {Y(ny)}, r: {r}}}")

    lines.append(f"  guide: {{type: guide, x: {X(0.50)}, y: {Y(0.36)}, r: 10}}")

    for name, (nx, ny) in (("ls", (0.26, 0.30)), ("rs", (0.66, 0.52))):
        r = max(12, sizes[name][0] // 2)
        lines.append(f"  {name}: {{type: stick, x: {X(nx)}, y: {Y(ny)}, r: {r}}}")

    arm = max(12, sizes["dpad"][0] // 2)
    lines.append(f"  dpad: {{type: dpad, x: {X(0.38)}, y: {Y(0.52)}, arm: {arm}}}")

    (OUT / "layout.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "skin.yml").write_text(
        "name: Neon Pad\n"
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
    shutil.copy2(SRC, OUT / "_source_ps.png")

    # 底板
    base = clean_alpha(crop(raw, (20, 36, 472, 336)))
    tb = alpha_bbox(base, thr=8, pad=1)
    if tb:
        base = crop(base, tb)
    save_png(base, OUT / "base.png")
    print("base", base.width(), base.height())

    sizes: Dict[str, Tuple[int, int]] = {}
    for name, box in INACTIVE.items():
        ib = pad_box(box, 1, w, h)
        ab = pad_box(shift(box, ACTIVE_DY, h), 1, w, h)
        iw, ih = export_part(raw, ib, OUT / "inactive" / f"{name}.png")
        aw, ah = export_part(raw, ab, OUT / "active" / f"{name}.png")
        sizes[name] = (iw, ih)
        print(f"  {name}: {iw}x{ih} / active {aw}x{ah}")

    write_meta(base.width(), base.height(), sizes)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
