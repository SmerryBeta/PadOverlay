"""手绘 Xbox 手柄：按 layout.yml 绘制与命中检测。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from display.layout import ControllerLayout, get_layout

COLOR_LINE = QColor(235, 238, 242, 230)
COLOR_DIM = QColor(120, 128, 140, 180)
COLOR_HL = QColor(0, 220, 200, 230)
COLOR_HL_FILL = QColor(0, 220, 200, 90)
COLOR_STICK_FILL = QColor(50, 55, 62, 200)
COLOR_SELECT = QColor(255, 200, 80, 120)


# 兼容旧引用
def _cw() -> int:
    return get_layout().canvas_w


def _ch() -> int:
    return get_layout().canvas_h


CANVAS_W = 520  # 默认；运行时以 get_layout().canvas_w 为准
CANVAS_H = 300


@dataclass
class HitZone:
    part: str
    kind: str  # "circle" | "rect"
    geom: Tuple[float, ...]
    # 拖拽用：布局部件名（摇杆四向 → ls/rs，十字 → dpad）
    drag_target: str = ""

    def contains(self, x: float, y: float) -> bool:
        if self.kind == "circle":
            cx, cy, r = self.geom
            return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
        x0, y0, w, h = self.geom
        return x0 <= x <= x0 + w and y0 <= y <= y0 + h


def build_hit_zones(layout: Optional[ControllerLayout] = None) -> List[HitZone]:
    from display.layout import part_metrics

    lay = layout or get_layout()
    zones: List[HitZone] = []
    for name, p in lay.parts.items():
        t = p.get("type")
        m = part_metrics(p)
        if t == "bumper":
            zones.append(
                HitZone(
                    name,
                    "rect",
                    (m["x"], m["y"], m["w"], m["h"]),
                    drag_target=name,
                )
            )
        elif t in ("face", "small"):
            r = m["r"] + (5 if t == "face" else 3)
            zones.append(
                HitZone(
                    name,
                    "circle",
                    (m["x"], m["y"], r),
                    drag_target=name,
                )
            )
        elif t == "stick":
            cx, cy, r = m["x"], m["y"], m["r"]
            prefix = name  # ls / rs
            # 整圆也可拖
            zones.append(
                HitZone(f"{prefix}_pad", "circle", (cx, cy, r), drag_target=prefix)
            )
            zones.append(
                HitZone(
                    f"{prefix}_up",
                    "rect",
                    (cx - 12, cy - r, 24, r * 0.5),
                    drag_target=prefix,
                )
            )
            zones.append(
                HitZone(
                    f"{prefix}_down",
                    "rect",
                    (cx - 12, cy + r * 0.5, 24, r * 0.5),
                    drag_target=prefix,
                )
            )
            zones.append(
                HitZone(
                    f"{prefix}_left",
                    "rect",
                    (cx - r, cy - 12, r * 0.5, 24),
                    drag_target=prefix,
                )
            )
            zones.append(
                HitZone(
                    f"{prefix}_right",
                    "rect",
                    (cx + r * 0.5, cy - 12, r * 0.5, 24),
                    drag_target=prefix,
                )
            )
        elif t == "dpad":
            cx, cy, arm = m["x"], m["y"], m["arm"]
            w = arm * 0.72
            zones.extend(
                [
                    HitZone(
                        "dpad_up",
                        "rect",
                        (cx - w / 2, cy - arm - w / 2, w, arm),
                        drag_target="dpad",
                    ),
                    HitZone(
                        "dpad_down",
                        "rect",
                        (cx - w / 2, cy + w / 2, w, arm),
                        drag_target="dpad",
                    ),
                    HitZone(
                        "dpad_left",
                        "rect",
                        (cx - arm - w / 2, cy - w / 2, arm, w),
                        drag_target="dpad",
                    ),
                    HitZone(
                        "dpad_right",
                        "rect",
                        (cx + w / 2, cy - w / 2, arm, w),
                        drag_target="dpad",
                    ),
                ]
            )
    # 面键 / 肩键优先于摇杆大圆：把 circle stick_pad 放到后面
    faces = [z for z in zones if not z.part.endswith("_pad")]
    pads = [z for z in zones if z.part.endswith("_pad")]
    return faces + pads


def hit_test(zones: List[HitZone], x: float, y: float) -> Optional[str]:
    for z in zones:
        if z.contains(x, y):
            # 映射用：摇杆 pad 不算按键
            if z.part.endswith("_pad"):
                continue
            return z.part
    return None


def hit_test_drag(zones: List[HitZone], x: float, y: float) -> Optional[str]:
    """布置模式：返回可拖拽的布局部件名。"""
    for z in zones:
        if z.contains(x, y) and z.drag_target:
            return z.drag_target
    return None


def _pen(hot: bool, width: float = 2.2) -> QPen:
    pen = QPen(COLOR_HL if hot else COLOR_LINE)
    pen.setWidthF(width + (1.2 if hot else 0))
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _on(active: Set[str], *names: str) -> bool:
    return any(n in active for n in names)


def draw_controller(
    p: QPainter,
    active: Set[str],
    stick_offsets: Dict[str, Tuple[float, float]],
    selected: Optional[str] = None,
    show_labels: bool = True,
    layout: Optional[ControllerLayout] = None,
) -> None:
    lay = layout or get_layout()

    # 主体轮廓（固定装饰，不进布局文件）
    body = QPainterPath()
    body.moveTo(108, 118)
    body.cubicTo(98, 72, 148, 50, 198, 54)
    body.lineTo(322, 54)
    body.cubicTo(372, 50, 422, 72, 412, 118)
    body.cubicTo(458, 148, 472, 210, 448, 252)
    body.cubicTo(422, 288, 378, 272, 358, 242)
    body.lineTo(162, 242)
    body.cubicTo(142, 272, 98, 288, 72, 252)
    body.cubicTo(48, 210, 62, 148, 108, 118)
    body.closeSubpath()
    p.setPen(_pen(False, 2.4))
    p.setBrush(Qt.NoBrush)
    p.drawPath(body)

    for name, part in lay.parts.items():
        t = part.get("type")
        if t == "bumper":
            rect = QRectF(
                float(part["x"]),
                float(part["y"]),
                float(part["w"]),
                float(part["h"]),
            )
            compact = float(part["h"]) <= 17
            _draw_bumper(
                p,
                rect,
                _on(active, name),
                str(part.get("label", name.upper())),
                selected == name,
                compact=compact,
            )
        elif t == "face":
            c = QPointF(float(part["x"]), float(part["y"]))
            _draw_face_button(
                p,
                c,
                float(part["r"]),
                str(part.get("label", "?")),
                _on(active, name),
                selected == name,
            )
        elif t == "small":
            _draw_small(
                p,
                QPointF(float(part["x"]), float(part["y"])),
                float(part["r"]),
                _on(active, name),
                selected == name,
            )
        elif t == "guide":
            _draw_guide(
                p,
                QPointF(float(part["x"]), float(part["y"])),
                float(part["r"]),
            )
        elif t == "stick":
            prefix = name
            dx, dy = stick_offsets.get(prefix, (0.0, 0.0))
            sel = selected if selected and (
                selected == name or selected.startswith(prefix + "_")
            ) else None
            _draw_stick(
                p,
                QPointF(float(part["x"]), float(part["y"])),
                float(part["r"]),
                dx,
                dy,
                _on(active, f"{prefix}_up", f"{prefix}_down", f"{prefix}_left", f"{prefix}_right"),
                sel if sel else (name if selected == name else None),
            )
        elif t == "dpad":
            _draw_dpad(
                p,
                QPointF(float(part["x"]), float(part["y"])),
                float(part.get("arm", 20)),
                active,
                selected,
            )

    if show_labels:
        p.setPen(COLOR_DIM)
        p.setFont(QFont("Microsoft YaHei", 7))


def _draw_bumper(
    p: QPainter,
    rect: QRectF,
    hot: bool,
    label: str,
    selected: bool = False,
    compact: bool = False,
) -> None:
    path = QPainterPath()
    path.addRoundedRect(rect, 6 if compact else 8, 6 if compact else 8)
    if selected:
        p.fillPath(path, COLOR_SELECT)
    elif hot:
        p.fillPath(path, COLOR_HL_FILL)
    p.setPen(_pen(hot or selected, 1.8 if compact else 2.0))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(COLOR_HL if hot else COLOR_DIM)
    p.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Bold))
    p.drawText(rect, Qt.AlignCenter, label)


def _draw_stick(
    p: QPainter,
    center: QPointF,
    radius: float,
    dx: float,
    dy: float,
    hot: bool,
    selected: Optional[str],
) -> None:
    ring = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
    if selected:
        p.setBrush(COLOR_SELECT)
    elif hot:
        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, QColor(0, 220, 200, 50))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
    else:
        p.setBrush(Qt.NoBrush)
    p.setPen(_pen(hot or bool(selected), 2.2))
    p.drawEllipse(ring)

    cap_r = radius * 0.42
    travel = radius * 0.40
    cap_c = QPointF(center.x() + dx * travel, center.y() + dy * travel)
    cap = QRectF(cap_c.x() - cap_r, cap_c.y() - cap_r, cap_r * 2, cap_r * 2)
    p.setBrush(COLOR_HL_FILL if hot else COLOR_STICK_FILL)
    p.setPen(_pen(hot, 1.8))
    p.drawEllipse(cap)


def _draw_dpad(
    p: QPainter, center: QPointF, arm: float, active: Set[str], selected: Optional[str]
) -> None:
    w = arm * 0.72
    parts = [
        ("dpad_up", QRectF(center.x() - w / 2, center.y() - arm - w / 2, w, arm)),
        ("dpad_down", QRectF(center.x() - w / 2, center.y() + w / 2, w, arm)),
        ("dpad_left", QRectF(center.x() - arm - w / 2, center.y() - w / 2, arm, w)),
        ("dpad_right", QRectF(center.x() + w / 2, center.y() - w / 2, arm, w)),
        ("_center", QRectF(center.x() - w / 2, center.y() - w / 2, w, w)),
    ]
    for name, rect in parts:
        hot = name in active
        sel = selected == name or selected == "dpad"
        path = QPainterPath()
        path.addRoundedRect(rect, 3, 3)
        if name != "_center" and (hot or sel):
            p.fillPath(path, COLOR_SELECT if sel else COLOR_HL_FILL)
        p.setPen(_pen((hot or sel) and name != "_center", 1.8))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def _draw_face_button(
    p: QPainter,
    center: QPointF,
    radius: float,
    label: str,
    hot: bool,
    selected: bool = False,
) -> None:
    rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
    path = QPainterPath()
    path.addEllipse(rect)
    if selected:
        p.fillPath(path, COLOR_SELECT)
    elif hot:
        p.fillPath(path, COLOR_HL_FILL)
    p.setPen(_pen(hot or selected, 2.0))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(COLOR_HL if hot else COLOR_LINE)
    p.setFont(QFont("Segoe UI", 9, QFont.Bold))
    p.drawText(rect, Qt.AlignCenter, label)


def _draw_small(
    p: QPainter, center: QPointF, radius: float, hot: bool, selected: bool = False
) -> None:
    rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
    if selected:
        p.setBrush(COLOR_SELECT)
    elif hot:
        p.setBrush(COLOR_HL_FILL)
    else:
        p.setBrush(Qt.NoBrush)
    p.setPen(_pen(hot or selected, 1.6))
    p.drawEllipse(rect)


def _draw_guide(p: QPainter, center: QPointF, radius: float) -> None:
    rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(False, 2.0))
    p.drawEllipse(rect)
    inset = radius * 0.35
    p.drawLine(
        QPointF(center.x() - inset, center.y() - inset),
        QPointF(center.x() + inset, center.y() + inset),
    )
    p.drawLine(
        QPointF(center.x() + inset, center.y() - inset),
        QPointF(center.x() - inset, center.y() + inset),
    )
