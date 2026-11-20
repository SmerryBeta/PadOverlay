"""从 neon 拼图裁切 skins/neon_pad。

源图自带 alpha：禁止按亮度抠图。
裁切后用 alpha 作掩码：RGB' = RGB * A / 255（预乘），A=0 处 RGB 清零。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt5.QtGui import QImage, qAlpha, qBlue, qGreen, qRed, qRgba
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path(
    r"C:\Users\30724\.cursor\projects\s-pyProjects-PadOverlay\assets"
    r"\Xbox__________-32d41a5f-bf5b-44c7-a8c8-cb6d2fb700a2.png"
)
LOCAL_SRC = ROOT / "skins" / "neon_pad" / "_source_sheet.png"
OUT = ROOT / "skins" / "neon_pad"
MID = 341

Box = Tuple[int, int, int, int]

# 部件框（INACTIVE 半边）；ACTIVE = y + MID。只作裁切范围，不改 alpha 形状。
PART_BOXES: Dict[str, Box] = {
    "btn_a": (478, 62, 531, 108),
    "btn_b": (547, 63, 597, 109),
    "btn_x": (616, 63, 666, 107),
    "btn_y": (682, 63, 733, 108),
    "lt": (768, 42, 850, 118),
    "rt": (890, 42, 970, 118),
    "lb": (488, 154, 592, 198),
    "rb": (614, 154, 712, 196),
    "btn_view": (746, 158, 808, 198),
    "btn_menu": (835, 158, 896, 198),
    "ls": (486, 236, 556, 298),
    "rs": (575, 236, 645, 298),
    "dpad": (670, 238, 746, 310),
    "dpad_up": (790, 236, 830, 274),
    "dpad_down": (780, 280, 846, 314),
    "dpad_left": (876, 252, 918, 294),
    "dpad_right": (958, 250, 1000, 294),
}


def alpha_bbox(
    img: QImage,
    *,
    x0: int = 0,
    y0: int = 0,
    x1: Optional[int] = None,
    y1: Optional[int] = None,
    thr: int = 1,
    pad: int = 0,
) -> Optional[Box]:
    w, h = img.width(), img.height()
    if x1 is None:
        x1 = w - 1
    if y1 is None:
        y1 = h - 1
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w - 1, x1), min(h - 1, y1)
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
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


def apply_alpha_mask(img: QImage) -> QImage:
    """保留源 alpha；A=0 处 RGB 清零（去掉透明区脏色）。

    真正的 RGB*=A/255 在加载时用 Format_ARGB32_Premultiplied 完成。
    这里绝不按亮度阈值抠图。
    """
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


def crop(img: QImage, box: Box) -> QImage:
    x0, y0, x1, y1 = box
    return img.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def shift(box: Box, dy: int, h: int) -> Box:
    x0, y0, x1, y1 = box
    return (x0, max(0, y0 + dy), x1, min(h - 1, y1 + dy))


def tighten(img: QImage) -> QImage:
    box = alpha_bbox(img, thr=1, pad=1)
    if not box:
        return img
    return crop(img, box)


def save_png(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise RuntimeError(f"save failed: {path}")


def write_meta(base: QImage) -> None:
    cw, ch = base.width(), base.height()
    (OUT / "skin.yml").write_text(
        "name: Neon Pad\n"
        "mode: image\n"
        "base: base.png\n"
        "active_dir: active\n"
        "inactive_dir: inactive\n",
        encoding="utf-8",
    )

    def X(n: float) -> int:
        return int(n * cw)

    def Y(n: float) -> int:
        return int(n * ch)

    def R(n: float) -> int:
        return max(6, int(n * cw))

    (OUT / "layout.yml").write_text(
        f"""# neon_pad — canvas 对齐 base.png ({cw}x{ch})

canvas:
  w: {cw}
  h: {ch}

parts:
  lt: {{type: bumper, x: {X(0.28)}, y: {Y(0.06)}, w: {X(0.14)}, h: {Y(0.07)}, label: LT}}
  rt: {{type: bumper, x: {X(0.58)}, y: {Y(0.06)}, w: {X(0.14)}, h: {Y(0.07)}, label: RT}}
  lb: {{type: bumper, x: {X(0.28)}, y: {Y(0.14)}, w: {X(0.14)}, h: {Y(0.055)}, label: LB}}
  rb: {{type: bumper, x: {X(0.58)}, y: {Y(0.14)}, w: {X(0.14)}, h: {Y(0.055)}, label: RB}}
  btn_y: {{type: face, x: {X(0.796)}, y: {Y(0.205)}, r: {R(0.035)}, label: Y}}
  btn_x: {{type: face, x: {X(0.733)}, y: {Y(0.294)}, r: {R(0.035)}, label: X}}
  btn_b: {{type: face, x: {X(0.859)}, y: {Y(0.294)}, r: {R(0.035)}, label: B}}
  btn_a: {{type: face, x: {X(0.796)}, y: {Y(0.389)}, r: {R(0.035)}, label: A}}
  btn_view: {{type: small, x: {X(0.445)}, y: {Y(0.290)}, r: {R(0.028)}}}
  btn_menu: {{type: small, x: {X(0.602)}, y: {Y(0.287)}, r: {R(0.028)}}}
  guide: {{type: guide, x: {X(0.525)}, y: {Y(0.369)}, r: {R(0.025)}}}
  ls: {{type: stick, x: {X(0.253)}, y: {Y(0.290)}, r: {R(0.073)}}}
  rs: {{type: stick, x: {X(0.660)}, y: {Y(0.525)}, r: {R(0.073)}}}
  dpad: {{type: dpad, x: {X(0.389)}, y: {Y(0.525)}, arm: {R(0.077)}}}
""",
        encoding="utf-8",
    )


def process_crop(raw: QImage, box: Box) -> QImage:
    """裁切 → alpha 掩码乘 RGB → 按 alpha 紧裁。"""
    piece = crop(raw, box)
    piece = apply_alpha_mask(piece)
    return tighten(piece)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        LOCAL_SRC if LOCAL_SRC.exists() else DEFAULT_SRC
    )
    raw = QImage(str(src_path))
    if raw.isNull():
        print("bad image", src_path)
        return 1
    raw = raw.convertToFormat(QImage.Format_ARGB32)
    w, h = raw.width(), raw.height()
    print(f"src {src_path} {w}x{h} hasAlpha={raw.hasAlphaChannel()}")

    # 底板：INACTIVE 左栏壳体（避开左上 INACTIVE 字样）
    mid = h // 2
    base_box = alpha_bbox(raw, x0=8, y0=36, x1=460, y1=mid - 8, thr=8, pad=1)
    if not base_box:
        raise RuntimeError("底板 alpha 区域为空")
    print("base_box", base_box)

    OUT.mkdir(parents=True, exist_ok=True)
    base = process_crop(raw, base_box)
    save_png(base, OUT / "base.png")
    print("base", base.width(), base.height())

    for name, box in PART_BOXES.items():
        inactive = process_crop(raw, box)
        active = process_crop(raw, shift(box, MID, h))
        save_png(inactive, OUT / "inactive" / f"{name}.png")
        save_png(active, OUT / "active" / f"{name}.png")
        print(f"  {name}: {inactive.width()}x{inactive.height()}")

    write_meta(base)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
