"""映射设置：深色界面 + 手柄点选/布置 + 映射表。"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QRectF, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QWheelEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from display.controller_draw import (
    build_hit_zones,
    hit_test,
    hit_test_drag,
)
from display.layout import get_layout, save_layout
from display.skin import get_skin, list_skins, set_skin
from display.skin_draw import BASE_SELECT, render_pad
from mapping.mapper import PART_LABELS, KeyMapper

PART_ORDER: List[str] = [
    "lt", "lb", "rt", "rb",
    "btn_y", "btn_x", "btn_b", "btn_a",
    "btn_view", "btn_menu",
    "ls_up", "ls_down", "ls_left", "ls_right",
    "rs_up", "rs_down", "rs_left", "rs_right",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
]

STYLE = """
QWidget#SettingsRoot {
    background: #1a1c20;
    color: #e6e8ec;
}
QLabel#HintLabel {
    color: #c5cad3;
    font-size: 13px;
    padding: 4px 2px;
}
QLabel#DetailLabel {
    color: #7d8794;
    font-family: Consolas, "Microsoft YaHei";
    font-size: 12px;
    padding: 2px;
}
QLabel#SectionTitle {
    color: #8b949e;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
}
QFrame#Card {
    background: #22252b;
    border: 1px solid #32363e;
    border-radius: 12px;
}
QTableWidget {
    background: #1e2126;
    alternate-background-color: #252830;
    color: #e6e8ec;
    gridline-color: #32363e;
    border: 1px solid #32363e;
    border-radius: 8px;
    selection-background-color: rgba(0, 220, 200, 55);
    selection-color: #ffffff;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background: #2a2e36;
    color: #9aa3ad;
    border: none;
    border-bottom: 1px solid #32363e;
    border-right: 1px solid #32363e;
    padding: 6px 8px;
    font-weight: bold;
}
QPushButton {
    background: #2c313a;
    color: #e6e8ec;
    border: 1px solid #3a404c;
    border-radius: 8px;
    padding: 8px 14px;
    min-height: 18px;
}
QPushButton:hover { background: #353b46; border-color: #4a5160; }
QPushButton:pressed { background: #262a32; }
QPushButton#PrimaryBtn {
    background: #0f6e66;
    border-color: #12a090;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover { background: #128a80; }
QPushButton#DangerBtn {
    background: #3a2a2a;
    border-color: #6a4040;
}
QPushButton#DangerBtn:hover { background: #4a3333; }
QCheckBox {
    color: #c5cad3;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid #4a5160;
    background: #2c313a;
}
QCheckBox::indicator:checked {
    background: #12a090;
    border-color: #12a090;
}
QComboBox {
    background: #2c313a;
    color: #e6e8ec;
    border: 1px solid #3a404c;
    border-radius: 8px;
    padding: 6px 10px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #22252b;
    color: #e6e8ec;
    selection-background-color: rgba(0, 220, 200, 55);
}
"""


class ControllerPicker(QWidget):
    part_clicked = pyqtSignal(str)
    layout_moved = pyqtSignal()

    _UNDO_MAX = 64

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = get_layout()
        self._zones = build_hit_zones(self._layout)
        self._selected: Optional[str] = None
        self._bound_parts: Set[str] = set()
        self._layout_edit = False
        self._drag_part: Optional[str] = None
        self._drag_off: Tuple[float, float] = (0.0, 0.0)
        self._drag_pushed = False
        self._undo_stack: List[Dict[str, Any]] = []
        self._redo_stack: List[Dict[str, Any]] = []
        self.setFixedSize(self._layout.canvas_w, self._layout.canvas_h)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def set_layout_edit(self, enabled: bool) -> None:
        self._layout_edit = enabled
        self._drag_part = None
        self._drag_pushed = False
        if enabled:
            self.clear_undo()
            self.setFocus(Qt.OtherFocusReason)
        self.setCursor(Qt.SizeAllCursor if enabled else Qt.PointingHandCursor)
        self.update()

    def clear_undo(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def refresh_zones(self) -> None:
        self._layout = get_layout()
        self._zones = build_hit_zones(self._layout)
        self.setFixedSize(self._layout.canvas_w, self._layout.canvas_h)
        self.clear_undo()
        self.update()

    def set_selected(self, part: Optional[str]) -> None:
        self._selected = part
        self.update()

    def set_bound_parts(self, parts: Set[str]) -> None:
        self._bound_parts = parts
        self.update()

    def _hint(self, text: str) -> None:
        parent = self.parent()
        while parent is not None and not hasattr(parent, "hint"):
            parent = parent.parent()
        if parent is not None and hasattr(parent, "hint"):
            parent.hint.setText(text)

    def _push_undo(self) -> None:
        snap = self._layout.snapshot()
        if self._undo_stack and self._undo_stack[-1] == snap:
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > self._UNDO_MAX:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._layout_edit or not self._undo_stack:
            return False
        self._redo_stack.append(self._layout.snapshot())
        self._layout.restore(self._undo_stack.pop())
        self._zones = build_hit_zones(self._layout)
        self.update()
        self.layout_moved.emit()
        self._hint("已撤销（Ctrl+Z）")
        return True

    def redo(self) -> bool:
        if not self._layout_edit or not self._redo_stack:
            return False
        self._undo_stack.append(self._layout.snapshot())
        self._layout.restore(self._redo_stack.pop())
        self._zones = build_hit_zones(self._layout)
        self.update()
        self.layout_moved.emit()
        self._hint("已重做（Ctrl+Y）")
        return True

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        x, y = float(event.x()), float(event.y())
        if self._layout_edit:
            self._drag_pushed = False
            target = hit_test_drag(self._zones, x, y)
            if target:
                part = self._layout.part(target)
                if not part:
                    return
                self._drag_part = target
                self._drag_off = (x - float(part["x"]), y - float(part["y"]))
                self._selected = target
                self.update()
                return
            # 点空白 / 底板区域 → 选中底板
            self._drag_part = BASE_SELECT
            self._drag_off = (x - self._layout.base_x, y - self._layout.base_y)
            self._selected = BASE_SELECT
            self.update()
            return

        part = hit_test(self._zones, x, y)
        if part:
            self.part_clicked.emit(part)

    def mouseMoveEvent(self, event) -> None:
        if not self._layout_edit or not self._drag_part:
            return
        if not self._drag_pushed:
            self._push_undo()
            self._drag_pushed = True
        x = float(event.x()) - self._drag_off[0]
        y = float(event.y()) - self._drag_off[1]
        x = max(-self.width(), min(self.width() - 8, x))
        y = max(-self.height(), min(self.height() - 8, y))
        if self._drag_part == BASE_SELECT:
            self._layout.move_base(x, y)
        else:
            self._layout.move_part(self._drag_part, x, y)
            self._zones = build_hit_zones(self._layout)
        self.update()
        self.layout_moved.emit()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_part = None
        self._drag_pushed = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        """布置：滚轮缩放；Shift+滚轮旋转。对象为选中按键，或未选按时为底板。"""
        if not self._layout_edit:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        target = self._drag_part or self._selected
        if not target:
            target = hit_test_drag(
                self._zones, float(event.x()), float(event.y())
            )
        if not target:
            target = BASE_SELECT

        self._push_undo()
        rotate = bool(event.modifiers() & Qt.ShiftModifier)
        if target == BASE_SELECT:
            if rotate:
                step = 5.0 if delta > 0 else -5.0
                ang = self._layout.rotate_base(step)
                self._hint(f"布置：底板 旋转 {ang:.0f}°（Shift+滚轮，记得保存布局）")
            else:
                factor = 1.1 if delta > 0 else (1.0 / 1.1)
                sc = self._layout.scale_base(factor)
                self._hint(f"布置：底板 缩放 {sc:.0%}（滚轮，记得保存布局）")
            self._selected = BASE_SELECT
        else:
            if rotate:
                step = 5.0 if delta > 0 else -5.0
                ang = self._layout.rotate_part(target, step)
                label = PART_LABELS.get(target, target)
                self._hint(
                    f"布置：{label} 旋转 {ang:.0f}°（Shift+滚轮，记得保存布局）"
                )
            else:
                factor = 1.1 if delta > 0 else (1.0 / 1.1)
                new_s = self._layout.scale_part(target, factor)
                label = PART_LABELS.get(target, target)
                self._hint(
                    f"布置：{label} 缩放 {new_s:.0%}（滚轮，记得保存布局）"
                )
            self._selected = target
            self._zones = build_hit_zones(self._layout)

        self.update()
        self.layout_moved.emit()
        event.accept()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self._layout.canvas_w, self._layout.canvas_h
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 0, w, h), 12, 12)
        p.fillPath(bg, QColor(24, 26, 30))
        # 布置模式选中布局部件名
        sel = self._selected
        if self._layout_edit and self._drag_part:
            sel = self._drag_part
        render_pad(
            p,
            self._bound_parts,
            {"ls": (0.0, 0.0), "rs": (0.0, 0.0)},
            selected=sel,
            show_labels=False,
            layout=self._layout,
        )
        if self._layout_edit:
            p.setPen(QColor(255, 200, 80, 200))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 12, 12)


class SettingsWindow(QWidget):
    mappings_saved = pyqtSignal()
    layout_saved = pyqtSignal()
    _capture_done = pyqtSignal(str, str)

    def __init__(
        self,
        mapper: KeyMapper,
        begin_capture: Callable[[Callable[[str], None]], None],
        cancel_capture: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.mapper = mapper
        self._begin_capture = begin_capture
        self._cancel_capture = cancel_capture
        self._waiting_part: Optional[str] = None
        self._draft: Dict[str, List[str]] = mapper.snapshot()
        self._syncing_table = False
        self._layout_dirty = False

        self.setObjectName("SettingsRoot")
        self.setWindowTitle("PadOverlay · 映射设置")
        self.setMinimumSize(920, 580)
        self.setStyleSheet(STYLE)
        self._capture_done.connect(self._apply_capture)
        self._build_ui()
        self._refresh_bound()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        self.hint = QLabel("点击左侧手柄按键，再按下要绑定的键盘 / 鼠标键")
        self.hint.setObjectName("HintLabel")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        body = QHBoxLayout()
        body.setSpacing(14)

        left_card = QFrame()
        left_card.setObjectName("Card")
        left_lay = QVBoxLayout(left_card)
        left_lay.setContentsMargins(12, 12, 12, 12)
        left_lay.setSpacing(8)

        head = QHBoxLayout()
        title_l = QLabel("HANDSET")
        title_l.setObjectName("SectionTitle")
        head.addWidget(title_l)
        head.addStretch(1)
        self.chk_layout = QCheckBox("布置布局（拖拽按键）")
        self.chk_layout.toggled.connect(self._on_layout_mode)
        head.addWidget(self.chk_layout)
        left_lay.addLayout(head)

        skin_row = QHBoxLayout()
        skin_lbl = QLabel("皮肤")
        skin_lbl.setObjectName("SectionTitle")
        skin_row.addWidget(skin_lbl)
        self.cmb_skin = QComboBox()
        self.cmb_skin.setMinimumWidth(220)
        self.cmb_skin.setToolTip("切换手柄外观（矢量 / 图片皮肤）")
        self.cmb_skin.currentIndexChanged.connect(self._on_skin_changed)
        skin_row.addWidget(self.cmb_skin, stretch=1)
        left_lay.addLayout(skin_row)
        self._reload_skin_list()

        self.picker = ControllerPicker()
        self.picker.part_clicked.connect(self._on_part_clicked)
        self.picker.layout_moved.connect(self._on_layout_moved)
        left_lay.addWidget(self.picker, alignment=Qt.AlignCenter)

        # 布置编辑：撤销 / 重做（窗口内全局快捷键）
        self._sc_undo = QShortcut(QKeySequence.Undo, self)
        self._sc_undo.activated.connect(self._undo_layout)
        self._sc_redo = QShortcut(QKeySequence.Redo, self)
        self._sc_redo.activated.connect(self._redo_layout)
        # 部分键盘 Redo 是 Ctrl+Y
        self._sc_redo_y = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._sc_redo_y.activated.connect(self._redo_layout)

        self.detail = QLabel("")
        self.detail.setObjectName("DetailLabel")
        left_lay.addWidget(self.detail)

        lay_btns = QHBoxLayout()
        btn_save_lay = QPushButton("保存布局")
        btn_save_lay.setObjectName("PrimaryBtn")
        btn_save_lay.clicked.connect(self._save_layout)
        btn_reload_lay = QPushButton("重载布局")
        btn_reload_lay.clicked.connect(self._reload_layout)
        lay_btns.addWidget(btn_save_lay)
        lay_btns.addWidget(btn_reload_lay)
        lay_btns.addStretch(1)
        left_lay.addLayout(lay_btns)

        body.addWidget(left_card, stretch=0)

        right_card = QFrame()
        right_card.setObjectName("Card")
        right_lay = QVBoxLayout(right_card)
        right_lay.setContentsMargins(12, 12, 12, 12)
        right_lay.setSpacing(8)
        title_r = QLabel("KEYMAP")
        title_r.setObjectName("SectionTitle")
        right_lay.addWidget(title_r)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["手柄部件", "物理键"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_lay.addWidget(self.table)
        body.addWidget(right_card, stretch=1)

        root.addLayout(body, stretch=1)

        row = QHBoxLayout()
        row.setSpacing(8)
        btn_clear = QPushButton("清除该键绑定")
        btn_clear.setObjectName("DangerBtn")
        btn_clear.clicked.connect(self._clear_selected)
        btn_cancel = QPushButton("取消等待")
        btn_cancel.clicked.connect(self._cancel_wait)
        btn_reload = QPushButton("从文件重载映射")
        btn_reload.clicked.connect(self._reload)
        btn_save = QPushButton("保存映射")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.clicked.connect(self._save)
        row.addWidget(btn_clear)
        row.addWidget(btn_cancel)
        row.addStretch(1)
        row.addWidget(btn_reload)
        row.addWidget(btn_save)
        root.addLayout(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 每次打开刷新皮肤列表（新增 skins/ 目录后无需重启）
        self._reload_skin_list()

    def _reload_skin_list(self) -> None:
        skins = list_skins()
        cur = get_skin().id
        self.cmb_skin.blockSignals(True)
        self.cmb_skin.clear()
        for sid, name in skins:
            self.cmb_skin.addItem(f"{name}  ·  {sid}", sid)
        idx = self.cmb_skin.findData(cur)
        if idx < 0 and self.cmb_skin.count() > 0:
            idx = 0
        if idx >= 0:
            self.cmb_skin.setCurrentIndex(idx)
        self.cmb_skin.blockSignals(False)

    def _on_layout_mode(self, on: bool) -> None:
        self._cancel_capture()
        self._waiting_part = None
        self.picker.set_layout_edit(on)
        if on:
            self.hint.setText(
                "布置：拖拽 · 滚轮缩放 · Shift+滚轮旋转 · 点空白选底板 · Ctrl+Z 撤销 · Ctrl+Y 重做"
            )
        else:
            self.hint.setText("点击左侧手柄按键，再按下要绑定的键盘 / 鼠标键")

    def _undo_layout(self) -> None:
        if self.chk_layout.isChecked():
            self.picker.undo()

    def _redo_layout(self) -> None:
        if self.chk_layout.isChecked():
            self.picker.redo()

    def _on_skin_changed(self, _index: int) -> None:
        sid = self.cmb_skin.currentData()
        if not sid:
            return
        sid = str(sid)
        if sid == get_skin().id:
            return
        if self._layout_dirty:
            ret = QMessageBox.question(
                self,
                "切换皮肤",
                "当前布局有未保存改动，切换皮肤将丢弃这些改动。继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                self._reload_skin_list()
                return
        try:
            sk = set_skin(sid)
        except FileNotFoundError as e:
            QMessageBox.warning(self, "皮肤", str(e))
            self._reload_skin_list()
            return
        self._layout_dirty = False
        if self.chk_layout.isChecked():
            self.chk_layout.setChecked(False)
        self.picker.refresh_zones()
        self.layout_saved.emit()  # 同步悬浮窗
        self.hint.setText(f"已切换皮肤：{sk.name}（{sk.id}）· mode={sk.mode}")

    def _on_layout_moved(self) -> None:
        self._layout_dirty = True

    def _save_layout(self) -> None:
        lay = get_layout()
        save_layout(lay)
        self._layout_dirty = False
        self.picker.refresh_zones()
        self.picker.clear_undo()
        self.layout_saved.emit()
        self.hint.setText(f"布局已写入 {lay.path.name}（当前皮肤目录），悬浮窗已同步。")

    def _reload_layout(self) -> None:
        get_skin(force_reload=True)
        get_layout(force_reload=True)
        self.picker.refresh_zones()
        self.picker.clear_undo()
        self._layout_dirty = False
        self.layout_saved.emit()
        self.hint.setText("已从当前皮肤目录重载布局。")

    def _bound_parts_from_draft(self) -> Set[str]:
        parts: Set[str] = set()
        for plist in self._draft.values():
            parts.update(plist)
        return parts

    def _keys_for_part_draft(self, part: str) -> List[str]:
        return [k for k, parts in self._draft.items() if part in parts]

    def _refresh_table(self) -> None:
        self._syncing_table = True
        bound = self._bound_parts_from_draft()
        ordered = [p for p in PART_ORDER if p in bound]
        extra = sorted(bound - set(PART_ORDER))
        rows = [(p, ", ".join(self._keys_for_part_draft(p))) for p in ordered + extra]

        self.table.setRowCount(len(rows))
        selected = self.picker._selected
        select_row = -1
        for i, (part, keys) in enumerate(rows):
            item0 = QTableWidgetItem(PART_LABELS.get(part, part))
            item0.setData(Qt.UserRole, part)
            self.table.setItem(i, 0, item0)
            self.table.setItem(i, 1, QTableWidgetItem(keys))
            if part == selected:
                select_row = i
        if select_row >= 0:
            self.table.selectRow(select_row)
        self._syncing_table = False

    def _refresh_bound(self) -> None:
        self.picker.set_bound_parts(self._bound_parts_from_draft())
        self._refresh_table()
        self._update_detail()

    def _update_detail(self) -> None:
        if self.chk_layout.isChecked():
            self.detail.setText("布置中 — 拖完后记得「保存布局」")
            return
        part = self._waiting_part or self.picker._selected
        if not part:
            self.detail.setText("未选择部件 — 点击手柄或表格一行")
            return
        label = PART_LABELS.get(part, part)
        keys = self._keys_for_part_draft(part)
        keys_txt = ", ".join(keys) if keys else "（无）"
        if self._waiting_part:
            self.hint.setText(f"等待按键：请按下要绑定到「{label}」的键盘或鼠标键…")
        else:
            self.hint.setText("点击左侧手柄按键，再按下要绑定的键盘 / 鼠标键")
        self.detail.setText(f"{label}  ←  {keys_txt}")

    def _on_table_select(self) -> None:
        if self._syncing_table or self.chk_layout.isChecked():
            return
        items = self.table.selectedItems()
        if not items:
            return
        part = self.table.item(items[0].row(), 0).data(Qt.UserRole)
        if not part:
            return
        self.picker.set_selected(part)
        self._update_detail()

    def _on_part_clicked(self, part: str) -> None:
        if self.chk_layout.isChecked():
            return
        self.picker.set_selected(part)
        self._waiting_part = part
        self._refresh_table()
        self._update_detail()

        def on_key(name: str) -> None:
            self._capture_done.emit(part, name)

        self._begin_capture(on_key)

    @pyqtSlot(str, str)
    def _apply_capture(self, part: str, key: str) -> None:
        for k in list(self._draft.keys()):
            if part in self._draft[k]:
                self._draft[k] = [p for p in self._draft[k] if p != part]
                if not self._draft[k]:
                    del self._draft[k]
        parts = self._draft.setdefault(key, [])
        if part not in parts:
            parts.append(part)
        self._waiting_part = None
        self.picker.set_selected(part)
        self._refresh_bound()
        label = PART_LABELS.get(part, part)
        self.hint.setText(f"已暂存：{label} ← {key}（点「保存映射」生效）")

    def _clear_selected(self) -> None:
        part = self.picker._selected
        if not part:
            QMessageBox.information(self, "提示", "请先点击手柄或表格中的一个按键。")
            return
        for k in list(self._draft.keys()):
            if part in self._draft[k]:
                self._draft[k] = [p for p in self._draft[k] if p != part]
                if not self._draft[k]:
                    del self._draft[k]
        self._waiting_part = None
        self._cancel_capture()
        self._refresh_bound()

    def _cancel_wait(self) -> None:
        self._waiting_part = None
        self._cancel_capture()
        self._update_detail()

    def _save(self) -> None:
        self.mapper._keys = {k: list(v) for k, v in self._draft.items()}
        self.mapper.save()
        self._cancel_capture()
        self._waiting_part = None
        self.mappings_saved.emit()
        self.hint.setText("映射已保存并热加载。")
        self._refresh_bound()

    def _reload(self) -> None:
        self.mapper.reload()
        self._draft = self.mapper.snapshot()
        self._waiting_part = None
        self._cancel_capture()
        self._refresh_bound()
        self.hint.setText("已从文件重载映射。")

    def closeEvent(self, event) -> None:
        self._cancel_capture()
        if self._layout_dirty:
            # 不强制保存，避免误写；提示即可
            self.hint.setText("布局有未保存改动，下次打开前请先「保存布局」。")
        super().closeEvent(event)
