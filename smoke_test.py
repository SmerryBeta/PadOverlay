"""短暂冒烟。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from display.controller_draw import build_hit_zones, hit_test, hit_test_drag
from display.layout import get_layout
from display.overlay import OverlayWindow
from listen.input_hook import InputHook
from mapping.mapper import KeyMapper
from mapping.pad_state import PadState
from ui.app_icon import make_app_icon


def main() -> None:
    lay = get_layout(force_reload=True)
    assert lay.part("lt") is not None
    zones = build_hit_zones(lay)
    lt = lay.part("lt")
    assert hit_test(zones, float(lt["x"]) + 5, float(lt["y"]) + 5) == "lt"
    assert hit_test_drag(zones, float(lt["x"]) + 5, float(lt["y"]) + 5) == "lt"

    mapper = KeyMapper()
    assert "r" in mapper.keys
    assert "btn_x" in mapper.keys["r"]
    assert "t" in mapper.keys and "dpad_right" in mapper.keys["t"]
    assert "g" in mapper.keys and "dpad_left" in mapper.keys["g"]

    app = QApplication([])
    state = PadState()
    ov = OverlayWindow(state)
    ov.show()
    ov.apply_saved_position()
    assert ov.isVisible()
    ov.reload_layout()

    hook = InputHook(mapper.snapshot(), state.press, state.release)
    hook.start(hwnd=int(ov.winId()))
    ov.set_mouse_poll(hook.poll_cursor)
    hook.poll_cursor()
    hook.stop()
    assert not make_app_icon().isNull()
    QTimer.singleShot(250, app.quit)
    app.exec_()
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
