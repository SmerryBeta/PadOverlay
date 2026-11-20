"""程序化生成 skins/drawn_pad 图片皮肤（base + active/inactive）。

用法:
  python tools/gen_drawn_pad_skin.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "skins" / "drawn_pad"
CANVAS_W, CANVAS_H = 520, 300

# 与 layout.yml 对齐的部件几何（中心或左上角）
PARTS = {
    "lt": {"type": "bumper", "x": 161, "y": 35, "w": 62, "h": 20, "label": "LT"},
    "rt": {"type": "bumper", "x": 296, "y": 34, "w": 62, "h": 20, "label": "RT"},
    "lb": {"type": "bumper", "x": 160, "y": 55, "w": 62, "h": 16, "label": "LB"},
    "rb": {"type": "bumper", "x": 296, "y": 55, "w": 62, "h": 16, "label": "RB"},
    "btn_y": {"type": "face", "x": 350, "y": 91, "r": 13, "label": "Y", "tint": QColor(210, 190, 60)},
    "btn_x": {"type": "face", "x": 325, "y": 114, "r": 13, "label": "X", "tint": QColor(80, 140, 220)},
    "btn_b": {"type": "face", "x": 375, "y": 114, "r": 13, "label": "B", "tint": QColor(210, 80, 70)},
    "btn_a": {"type": "face", "x": 349, "y": 139, "r": 13, "label": "A", "tint": QColor(70, 180, 100)},
    "btn_view": {"type": "small", "x": 238, "y": 150, "r": 8, "label": "⧉"},
    "btn_menu": {"type": "small", "x": 285, "y": 149, "r": 8, "label": "☰"},
    "ls": {"type": "stick", "x": 164, "y": 124, "r": 30},
    "rs": {"type": "stick", "x": 347, "y": 192, "r": 30},
    "dpad": {"type": "dpad", "x": 158, "y": 201, "arm": 20},
}

ACCENT = QColor(0, 220, 200)
SHELL = QColor(36, 40, 48)
SHELL_EDGE = QColor(18, 20, 24)
WELL = QColor(22, 24, 28)


def _new_img(w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    return img


def _save(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(path), "PNG"):
        raise RuntimeError(f"保存失败: {path}")


def draw_base() -> QImage:
    img = _new_img(CANVAS_W, CANVAS_H)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    # 主体轮廓（左右握把 + 中央）
    body = QPainterPath()
    body.moveTo(110, 70)
    body.cubicTo(90, 55, 70, 70, 62, 110)
    body.cubicTo(48, 175, 55, 250, 95, 275)
    body.cubicTo(130, 292, 175, 275, 195, 245)
    body.cubicTo(210, 225, 225, 210, 250, 208)
    body.cubicTo(275, 210, 295, 225, 310, 245)
    body.cubicTo(330, 275, 375, 292, 410, 275)
    body.cubicTo(450, 250, 458, 175, 444, 110)
    body.cubicTo(436, 70, 416, 55, 396, 70)
    body.cubicTo(360, 55, 300, 48, 260, 48)
    body.cubicTo(220, 48, 150, 55, 110, 70)
    body.closeSubpath()

    grad = QRadialGradient(QPointF(260, 150), 220)
    grad.setColorAt(0.0, QColor(52, 58, 68))
    grad.setColorAt(0.55, SHELL)
    grad.setColorAt(1.0, SHELL_EDGE)
    p.fillPath(body, grad)

    pen = QPen(QColor(70, 78, 92, 180))
    pen.setWidthF(2.2)
    p.setPen(pen)
    p.drawPath(body)

    # 肩键槽
    for x, y, w, h in ((158, 28, 68, 14), (294, 28, 68, 14), (158, 48, 66, 10), (296, 48, 66, 10)):
        p.setPen(Qt.NoPen)
        p.setBrush(WELL)
        p.drawRoundedRect(QRectF(x, y, w, h), 5, 5)

    # 摇杆井
    for cx, cy, r in ((164, 124, 36), (347, 192, 36)):
        p.setBrush(WELL)
        p.setPen(QPen(QColor(12, 14, 16), 1.5))
        p.drawEllipse(QPointF(cx, cy), r, r)
        ring = QPen(QColor(60, 68, 80, 160))
        ring.setWidthF(2.0)
        p.setPen(ring)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r - 3, r - 3)

    # dpad 井
    dx, dy, arm = 158, 201, 24
    p.setPen(Qt.NoPen)
    p.setBrush(WELL)
    for rect in (
        QRectF(dx - 8, dy - arm, 16, arm * 2),
        QRectF(dx - arm, dy - 8, arm * 2, 16),
    ):
        p.drawRoundedRect(rect, 3, 3)

    # 面键浅井
    for cx, cy in ((350, 91), (325, 114), (375, 114), (349, 139)):
        p.setBrush(QColor(28, 30, 36))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 16, 16)

    # 中心装饰
    p.setBrush(QColor(44, 50, 60))
    p.setPen(QPen(QColor(80, 90, 105), 1.5))
    p.drawEllipse(QPointF(260, 178), 14, 14)
    p.setPen(QPen(ACCENT, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(260, 178), 8, 8)

    # 微高光
    p.setPen(Qt.NoPen)
    highlight = QColor(255, 255, 255, 22)
    p.setBrush(highlight)
    p.drawEllipse(QRectF(140, 70, 180, 40))

    p.end()
    return img


def _paint_circle_button(
    p: QPainter,
    cx: float,
    cy: float,
    r: float,
    *,
    active: bool,
    label: str = "",
    tint: Optional[QColor] = None,
) -> None:
    base = QColor(58, 64, 74) if not active else QColor(0, 160, 150)
    if tint is not None and not active:
        base = QColor(
            (base.red() + tint.red()) // 2,
            (base.green() + tint.green()) // 2,
            (base.blue() + tint.blue()) // 2,
        )
    elif tint is not None and active:
        base = tint.lighter(120)

    g = QRadialGradient(QPointF(cx - r * 0.25, cy - r * 0.3), r * 1.2)
    g.setColorAt(0.0, base.lighter(130))
    g.setColorAt(0.7, base)
    g.setColorAt(1.0, base.darker(140))
    p.setPen(QPen(base.darker(160), 1.2))
    p.setBrush(g)
    p.drawEllipse(QPointF(cx, cy), r, r)

    if active:
        glow = QPen(ACCENT)
        glow.setWidthF(2.0)
        p.setPen(glow)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r + 1.5, r + 1.5)

    if label:
        p.setPen(QColor(235, 238, 245) if not active else QColor(255, 255, 255))
        font = QFont("Segoe UI", max(8, int(r * 0.85)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, label)


def _paint_bumper(
    p: QPainter,
    rect: QRectF,
    *,
    active: bool,
    label: str,
) -> None:
    color = QColor(70, 78, 90) if not active else QColor(0, 180, 165)
    p.setPen(QPen(color.darker(150), 1.0))
    p.setBrush(color if not active else ACCENT)
    p.drawRoundedRect(rect, 5, 5)
    p.setPen(QColor(230, 234, 240) if not active else QColor(10, 30, 28))
    font = QFont("Segoe UI", 8)
    font.setBold(True)
    p.setFont(font)
    p.drawText(rect, Qt.AlignCenter, label)


def _paint_stick(p: QPainter, cx: float, cy: float, r: float, *, active: bool) -> None:
    well = QColor(40, 44, 52)
    p.setPen(QPen(QColor(20, 22, 26), 1.5))
    p.setBrush(well)
    p.drawEllipse(QPointF(cx, cy), r, r)

    cap_r = r * 0.62
    cap = ACCENT if active else QColor(90, 98, 110)
    g = QRadialGradient(QPointF(cx - cap_r * 0.2, cy - cap_r * 0.25), cap_r)
    g.setColorAt(0.0, cap.lighter(140))
    g.setColorAt(1.0, cap.darker(120))
    p.setPen(QPen(cap.darker(150), 1.2))
    p.setBrush(g)
    p.drawEllipse(QPointF(cx, cy), cap_r, cap_r)

    # 纹理点
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 40 if not active else 70))
    for i in range(6):
        ang = i * math.pi / 3
        px = cx + math.cos(ang) * cap_r * 0.45
        py = cy + math.sin(ang) * cap_r * 0.45
        p.drawEllipse(QPointF(px, py), 1.6, 1.6)


def _paint_dpad_base(p: QPainter, cx: float, cy: float, arm: float, *, active: bool) -> None:
    color = QColor(55, 60, 70) if not active else QColor(0, 140, 130)
    p.setPen(QPen(color.darker(150), 1.2))
    p.setBrush(color)
    for rect in (
        QRectF(cx - 7, cy - arm, 14, arm * 2),
        QRectF(cx - arm, cy - 7, arm * 2, 14),
    ):
        p.drawRoundedRect(rect, 3, 3)
    p.setBrush(color.darker(110))
    p.drawEllipse(QPointF(cx, cy), 5, 5)


def _paint_dpad_arm(
    p: QPainter,
    rect: QRectF,
    *,
    active: bool,
) -> None:
    color = QColor(70, 76, 88) if not active else ACCENT
    p.setPen(QPen(color.darker(140), 1.0))
    p.setBrush(color)
    p.drawRoundedRect(rect, 3, 3)


def make_part_image(part_id: str, meta: dict, *, active: bool) -> QImage:
    t = meta["type"]
    if t == "bumper":
        w, h = int(meta["w"]), int(meta["h"])
        img = _new_img(w, h)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        _paint_bumper(p, QRectF(0.5, 0.5, w - 1, h - 1), active=active, label=meta.get("label", ""))
        p.end()
        return img

    if t in ("face", "small"):
        r = float(meta["r"])
        size = int(math.ceil(r * 2 + 4))
        img = _new_img(size, size)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx = cy = size / 2
        _paint_circle_button(
            p,
            cx,
            cy,
            r,
            active=active,
            label=str(meta.get("label", "")),
            tint=meta.get("tint"),
        )
        p.end()
        return img

    if t == "stick":
        r = float(meta["r"])
        size = int(math.ceil(r * 2 + 4))
        img = _new_img(size, size)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        _paint_stick(p, size / 2, size / 2, r, active=active)
        p.end()
        return img

    if t == "dpad":
        arm = float(meta["arm"])
        size = int(math.ceil(arm * 2 + 8))
        img = _new_img(size, size)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        _paint_dpad_base(p, size / 2, size / 2, arm, active=active)
        p.end()
        return img

    raise ValueError(part_id)


def make_dpad_direction(direction: str, arm: float, *, active: bool) -> QImage:
    w = max(12, int(arm * 0.72))
    h = int(arm)
    if direction in ("left", "right"):
        w, h = h, w
    img = _new_img(w, h)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    _paint_dpad_arm(p, QRectF(0.5, 0.5, w - 1, h - 1), active=active)
    p.end()
    return img


def generate() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    active_dir = OUT / "active"
    inactive_dir = OUT / "inactive"
    active_dir.mkdir(exist_ok=True)
    inactive_dir.mkdir(exist_ok=True)

    _save(draw_base(), OUT / "base.png")

    for pid, meta in PARTS.items():
        _save(make_part_image(pid, meta, active=False), inactive_dir / f"{pid}.png")
        _save(make_part_image(pid, meta, active=True), active_dir / f"{pid}.png")

    arm = float(PARTS["dpad"]["arm"])
    for d in ("up", "down", "left", "right"):
        pid = f"dpad_{d}"
        _save(make_dpad_direction(d, arm, active=False), inactive_dir / f"{pid}.png")
        _save(make_dpad_direction(d, arm, active=True), active_dir / f"{pid}.png")

    print(f"generated skin at {OUT}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
