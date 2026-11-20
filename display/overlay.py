"""显示层：手柄外视觉透明；悬停显示 chrome。

Windows 分层窗（WA_TranslucentBackground）对 alpha=0 像素不做命中测试
（MSDN Layered Windows / Qt Forum）。线稿之间的空隙也是 alpha=0，
因此不能依赖 mouseEnter。做法：
1) 在 paintEvent 给手柄区/chrome 区铺 alpha=1 底色（人眼不可见，但可命中）
2) 用 QCursor 全局坐标定时判断悬停（不依赖 move 事件）
"""
from __future__ import annotations

from typing import Callable, Optional, Set

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QPainter, QWheelEvent
from PyQt5.QtWidgets import QApplication, QToolButton, QWidget

from display.layout import get_layout
from display.skin_draw import render_pad
from display.window_prefs import clamp_pos, load_prefs, save_prefs
from mapping.pad_state import PadState

PAD = 14
TIP_H = 26
TOP_BAR = 28
BTN = 22
SCALE_MIN = 0.55
SCALE_MAX = 2.8
GRIP = 14
# 分层窗命中用：>0 即可；略抬高避免部分驱动把 1 当成 0
HIT_ALPHA = 8


class _CursorFilter(QObject):
    """应用级鼠标移动过滤，光标一动就刷新悬停。"""

    def __init__(self, overlay: "OverlayWindow") -> None:
        super().__init__(overlay)
        self._overlay = overlay

    def eventFilter(self, obj, event) -> bool:
        et = event.type()
        if et in (QEvent.MouseMove, QEvent.HoverMove, QEvent.Enter, QEvent.Leave):
            self._overlay._refresh_chrome()
        return False


class OverlayWindow(QWidget):
    settings_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, state: PadState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self._drag_pos: Optional[QPoint] = None
        self._drag_enabled = True
        self._active_cache: Set[str] = set()
        self._scale = 1.0
        self._resizing = False
        self._resize_origin = QPoint()
        self._resize_start_scale = 1.0
        self._show_top_chrome = False
        self._show_bottom_chrome = False
        self._mouse_poll: Optional[Callable[[], None]] = None

        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self._persist_now)

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumSize(self._size_for_scale(SCALE_MIN))

        self._btn_settings = self._make_btn("⚙", "映射设置")
        self._btn_settings.clicked.connect(self.settings_requested.emit)
        self._btn_close = self._make_btn("✕", "退出程序")
        self._btn_close.clicked.connect(self.close_requested.emit)
        self._set_top_chrome_visible(False)

        prefs = load_prefs()
        self._apply_scale(float(prefs["scale"]), persist=False)
        self._place_buttons()
        # 位置在 show 后应用，便于按真实尺寸夹到可见屏幕
        self._pending_pos = (int(prefs["x"]), int(prefs["y"]))

        self._filter = _CursorFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._filter)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_mouse_poll(self, cb: Optional[Callable[[], None]]) -> None:
        self._mouse_poll = cb

    def apply_saved_position(self) -> None:
        """show 之后调用：恢复并夹紧上次位置。"""
        x, y = getattr(self, "_pending_pos", (80, 80))
        x, y = clamp_pos(x, y, self.width(), self.height())
        self.move(x, y)
        self._pending_pos = (x, y)

    def _make_btn(self, text: str, tip: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setFixedSize(BTN, BTN)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMouseTracking(True)
        btn.setAttribute(Qt.WA_Hover, True)
        btn.setStyleSheet(
            """
            QToolButton {
                color: #e8eaef;
                background: rgba(20, 22, 26, 200);
                border: 1px solid rgba(255,255,255,70);
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                color: #ffffff;
                background: rgba(0, 220, 200, 140);
                border-color: rgba(0, 220, 200, 220);
            }
            QToolButton:pressed {
                background: rgba(0, 220, 200, 180);
            }
            """
        )
        return btn

    def _size_for_scale(self, scale: float) -> QSize:
        lay = get_layout()
        w = int(lay.canvas_w * scale) + PAD * 2
        h = int(lay.canvas_h * scale) + PAD * 2 + TIP_H + TOP_BAR
        return QSize(w, h)

    def _pad_hit_rect(self) -> QRect:
        """手柄可命中/可悬停区域（含顶部栏，便于露出设置按钮）。"""
        lay = get_layout()
        pw = int(lay.canvas_w * self._scale)
        ph = int(lay.canvas_h * self._scale)
        return QRect(PAD, PAD, pw, ph + TOP_BAR)

    def _top_chrome_rect(self) -> QRect:
        return QRect(self.width() - BTN * 2 - 56, 0, BTN * 2 + 56, TOP_BAR + 20)

    def _bottom_chrome_rect(self) -> QRect:
        return QRect(0, self.height() - TIP_H - GRIP - 20, self.width(), TIP_H + GRIP + 20)

    def _to_global(self, local: QRect) -> QRect:
        return QRect(self.mapToGlobal(local.topLeft()), local.size())

    def reload_layout(self) -> None:
        from display.skin import get_skin

        get_skin(force_reload=True)
        get_layout(force_reload=True)
        self._active_cache = set()
        self._apply_scale(self._scale, persist=False)
        self.update()

    def _apply_scale(self, scale: float, *, persist: bool = True) -> None:
        self._scale = max(SCALE_MIN, min(SCALE_MAX, scale))
        self.setFixedSize(self._size_for_scale(self._scale))
        self._place_buttons()
        self.update()
        if persist:
            self._schedule_persist()

    def _place_buttons(self) -> None:
        margin = 8
        self._btn_close.move(self.width() - margin - BTN, margin)
        self._btn_settings.move(self.width() - margin - BTN * 2 - 6, margin)
        self._btn_close.raise_()
        self._btn_settings.raise_()

    def _set_top_chrome_visible(self, visible: bool) -> None:
        if self._show_top_chrome == visible:
            if visible:
                self._btn_settings.show()
                self._btn_close.show()
                self._btn_settings.raise_()
                self._btn_close.raise_()
            return
        self._show_top_chrome = visible
        self._btn_settings.setVisible(visible)
        self._btn_close.setVisible(visible)
        if visible:
            self._btn_settings.raise_()
            self._btn_close.raise_()
        self.update()

    def _set_bottom_chrome_visible(self, visible: bool) -> None:
        if self._show_bottom_chrome == visible:
            return
        self._show_bottom_chrome = visible
        self.update()

    def _refresh_chrome(self) -> None:
        """屏幕坐标判断悬停（分层窗透明区收不到 move，必须轮询）。"""
        if not self.isVisible():
            return
        gp = QCursor.pos()
        pad_g = self._to_global(self._pad_hit_rect())
        top_g = self._to_global(self._top_chrome_rect())
        bot_g = self._to_global(self._bottom_chrome_rect())

        on_btn = False
        for b in (self._btn_settings, self._btn_close):
            if b.isVisible():
                br = QRect(b.mapToGlobal(QPoint(0, 0)), b.size())
                if br.contains(gp):
                    on_btn = True
                    break

        over = (
            pad_g.contains(gp)
            or top_g.contains(gp)
            or bot_g.contains(gp)
            or on_btn
            or self._resizing
        )
        if not over:
            self._set_top_chrome_visible(False)
            self._set_bottom_chrome_visible(False)
            return

        # 悬停在手柄任意位置即显示顶部按钮与底部提示
        self._set_top_chrome_visible(True)
        self._set_bottom_chrome_visible(True)

    def set_drag_enabled(self, enabled: bool) -> None:
        self._drag_enabled = enabled

    def set_scale(self, scale: float) -> None:
        self._apply_scale(scale)

    def scale(self) -> float:
        return self._scale

    def _schedule_persist(self) -> None:
        self._persist_timer.start(280)

    def _persist_now(self) -> None:
        pos = self.pos()
        save_prefs(scale=self._scale, x=pos.x(), y=pos.y())

    def _tick(self) -> None:
        if self._mouse_poll is not None:
            try:
                self._mouse_poll()
            except Exception:
                pass
        self._refresh_chrome()
        stick_moving = self.state.tick_smooth(dt=1.0 / 30.0)
        active = self.state.active()
        if (
            stick_moving
            or active != self._active_cache
            or any(p.startswith(("ls_", "rs_")) for p in active)
            or self._show_top_chrome
            or self._show_bottom_chrome
        ):
            self._active_cache = active
            self.update()

    def _grip_rect(self) -> QRect:
        return QRect(self.width() - GRIP - 4, self.height() - GRIP - 4, GRIP, GRIP)

    def closeEvent(self, event) -> None:
        self._persist_now()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._filter)
        super().closeEvent(event)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        # 拖动过程中防抖写入，避免只靠 mouseRelease 漏存
        if self._drag_pos is not None or self._resizing:
            self._schedule_persist()

    def hideEvent(self, event) -> None:
        self._persist_now()
        super().hideEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 0.08 if delta > 0 else -0.08
        self._apply_scale(self._scale + step)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._refresh_chrome()
        if self._grip_rect().contains(event.pos()):
            self._resizing = True
            self._resize_origin = event.globalPos()
            self._resize_start_scale = self._scale
            self._set_bottom_chrome_visible(True)
            event.accept()
            return
        if self._drag_enabled:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        self._refresh_chrome()
        if self._resizing:
            dx = event.globalPos().x() - self._resize_origin.x()
            dy = event.globalPos().y() - self._resize_origin.y()
            delta = (dx + dy) / 2.0
            self._apply_scale(
                self._resize_start_scale + delta / 280.0, persist=False
            )
            event.accept()
            return
        if self._show_bottom_chrome and self._grip_rect().contains(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._drag_enabled:
            self.setCursor(Qt.ArrowCursor)
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        was_resize = self._resizing
        was_move = self._drag_pos is not None
        self._drag_pos = None
        self._resizing = False
        if was_resize or was_move:
            self._persist_now()
        self._refresh_chrome()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # chrome 热区需要极低 alpha 才能命中；图片皮肤底板自带 alpha，勿整块铺黑底
        # （否则会透过软边/开孔露出脏边，像狗啃）
        hit = QColor(0, 0, 0, HIT_ALPHA)
        from display.skin import get_skin

        sk = get_skin()
        if sk.mode != "image" or sk.base is None:
            painter.fillRect(QRectF(self._pad_hit_rect()), hit)
        painter.fillRect(QRectF(self._top_chrome_rect()), hit)
        painter.fillRect(QRectF(self._bottom_chrome_rect()), hit)

        painter.save()
        painter.translate(PAD, PAD + TOP_BAR)
        painter.scale(self._scale, self._scale)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        active = self.state.active()
        offsets = {
            "ls": self.state.stick_offset("ls"),
            "rs": self.state.stick_offset("rs"),
        }
        render_pad(painter, active, offsets, selected=None, show_labels=False)
        painter.restore()

        if self._show_bottom_chrome:
            painter.fillRect(
                QRectF(6, self.height() - TIP_H - 6, self.width() - 12, TIP_H),
                QColor(20, 22, 26, 170),
            )
            painter.setPen(QColor(220, 224, 230, 230))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(
                QRectF(
                    PAD,
                    self.height() - TIP_H - 2,
                    self.width() - PAD * 2 - GRIP,
                    TIP_H,
                ),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"拖动移动 · 滚轮缩放 {self._scale:.0%} · 右下角拖缩放",
            )
            grip = self._grip_rect()
            painter.setPen(QColor(0, 220, 200, 200))
            for i in range(3):
                o = i * 3
                painter.drawLine(
                    grip.right() - 2 - o,
                    grip.bottom() - 2,
                    grip.right() - 2,
                    grip.bottom() - 2 - o,
                )
