"""图片皮肤绘制：base + inactive/active 图层（支持底板/按键缩放与旋转）。"""
from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QImage, QPainter

from display.controller_draw import draw_controller
from display.layout import (
    ControllerLayout,
    get_layout,
    part_anchor,
    part_metrics,
    part_rot,
)
from display.skin import Skin, get_skin

BASE_SELECT = "__base__"


def _part_rect(part: dict) -> QRectF:
    m = part_metrics(part)
    t = part.get("type")
    x, y = m["x"], m["y"]
    if t == "bumper":
        return QRectF(x, y, m["w"], m["h"])
    if t == "dpad":
        arm = m["arm"]
        return QRectF(x - arm, y - arm, arm * 2, arm * 2)
    r = m["r"]
    return QRectF(x - r, y - r, r * 2, r * 2)


def _blit(p: QPainter, img: QImage, rect: QRectF) -> None:
    p.drawImage(rect, img, QRectF(img.rect()))


def _blit_rotated(
    p: QPainter,
    img: QImage,
    rect: QRectF,
    degrees: float,
    center: Optional[QPointF] = None,
) -> None:
    if abs(degrees) < 0.05:
        _blit(p, img, rect)
        return
    c = center or rect.center()
    p.save()
    p.translate(c)
    p.rotate(degrees)
    p.translate(-c)
    _blit(p, img, rect)
    p.restore()


def _draw_part_images(
    p: QPainter,
    skin: Skin,
    part_id: str,
    part: dict,
    pressed: bool,
    offset: Tuple[float, float] = (0.0, 0.0),
) -> None:
    rect = _part_rect(part)
    if offset != (0.0, 0.0):
        r = part_metrics(part)["r"]
        ox = offset[0] * r * 0.42
        oy = offset[1] * r * 0.42
        rect = rect.translated(ox, oy)
    inactive = skin.inactive_img(part_id)
    active = skin.active_img(part_id)
    rot = part_rot(part)
    ax, ay = part_anchor(part)
    center = QPointF(ax, ay)
    if offset != (0.0, 0.0):
        center = rect.center()

    if not pressed:
        img = inactive if inactive is not None else None
        if img is not None:
            _blit_rotated(p, img, rect, rot, center)
        return
    img = active if active is not None else inactive
    if img is not None:
        _blit_rotated(p, img, rect, rot, center)


def base_draw_rect(lay: ControllerLayout, skin: Skin) -> QRectF:
    """底板在画布上的轴对齐包围（未旋转前的放置矩形）。"""
    if skin.base is None:
        return QRectF(0, 0, lay.canvas_w, lay.canvas_h)
    s = lay.base_scale
    bw = skin.base.width() * s
    bh = skin.base.height() * s
    return QRectF(lay.base_x, lay.base_y, bw, bh)


def draw_image_skin(
    p: QPainter,
    active: Set[str],
    stick_offsets: Dict[str, Tuple[float, float]],
    selected: Optional[str] = None,
    layout: Optional[ControllerLayout] = None,
    skin: Optional[Skin] = None,
) -> None:
    lay = layout or get_layout()
    sk = skin or get_skin()

    # 底图：偏移 + 缩放 + 绕中心旋转
    if sk.base is not None:
        rect = base_draw_rect(lay, sk)
        rot = lay.base_rot
        p.save()
        if abs(rot) >= 0.05:
            c = rect.center()
            p.translate(c)
            p.rotate(rot)
            p.translate(-c)
        p.drawImage(rect, sk.base, QRectF(sk.base.rect()))
        p.restore()

    for name, part in lay.parts.items():
        t = part.get("type")
        if t == "guide":
            continue
        if t == "stick":
            pressed = any(
                f"{name}_{d}" in active for d in ("up", "down", "left", "right")
            ) or (selected == name)
            _draw_part_images(
                p, sk, name, part, pressed, stick_offsets.get(name, (0.0, 0.0))
            )
            continue
        if t == "dpad":
            _draw_part_images(p, sk, "dpad", part, False)
            for d in ("up", "down", "left", "right"):
                pid = f"dpad_{d}"
                hot = pid in active or selected == pid or selected == "dpad"
                if sk.inactive_img(pid) or sk.active_img(pid):
                    m = part_metrics(part)
                    cx, cy, arm = m["x"], m["y"], m["arm"]
                    w = arm * 0.72
                    boxes = {
                        "up": QRectF(cx - w / 2, cy - arm - w / 2, w, arm),
                        "down": QRectF(cx - w / 2, cy + w / 2, w, arm),
                        "left": QRectF(cx - arm - w / 2, cy - w / 2, arm, w),
                        "right": QRectF(cx + w / 2, cy - w / 2, arm, w),
                    }
                    rect = boxes[d]
                    img = sk.active_img(pid) if hot else sk.inactive_img(pid)
                    if hot and sk.active_img(pid) is None:
                        img = sk.inactive_img(pid)
                    if img is not None:
                        # 方向键随 dpad 整体旋转
                        _blit_rotated(
                            p, img, rect, part_rot(part), QPointF(cx, cy)
                        )
            continue

        hot = name in active or selected == name
        _draw_part_images(p, sk, name, part, hot)

    # 选中框（布置模式）
    if selected == BASE_SELECT and sk.base is not None:
        from display.controller_draw import COLOR_SELECT
        from PyQt5.QtGui import QPen

        rect = base_draw_rect(lay, sk)
        pen = QPen(COLOR_SELECT)
        pen.setWidthF(2.0)
        p.save()
        if abs(lay.base_rot) >= 0.05:
            c = rect.center()
            p.translate(c)
            p.rotate(lay.base_rot)
            p.translate(-c)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        p.restore()
    elif selected and selected in lay.parts:
        from display.controller_draw import COLOR_SELECT
        from PyQt5.QtGui import QPen

        part = lay.parts[selected]
        rect = _part_rect(part)
        pen = QPen(COLOR_SELECT)
        pen.setWidthF(2.0)
        p.save()
        rot = part_rot(part)
        if abs(rot) >= 0.05:
            ax, ay = part_anchor(part)
            p.translate(ax, ay)
            p.rotate(rot)
            p.translate(-ax, -ay)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        p.restore()


def render_pad(
    p: QPainter,
    active: Set[str],
    stick_offsets: Dict[str, Tuple[float, float]],
    selected: Optional[str] = None,
    show_labels: bool = False,
    layout: Optional[ControllerLayout] = None,
) -> None:
    """统一入口：按当前皮肤 mode 分发。"""
    sk = get_skin()
    if sk.mode == "image" and (
        sk.base is not None or sk.active_img("btn_a") or sk.inactive_img("btn_a")
    ):
        draw_image_skin(p, active, stick_offsets, selected, layout, sk)
        if sk.base is None and not sk._active and not sk._inactive:
            draw_controller(p, active, stick_offsets, selected, show_labels, layout)
    else:
        draw_controller(p, active, stick_offsets, selected, show_labels, layout)
