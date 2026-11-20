"""悬浮窗缩放与位置持久化。"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import yaml

from app_paths import ROOT

PREFS_PATH = ROOT / "config" / "window.yml"

DEFAULTS: Dict[str, Any] = {
    "scale": 1.0,
    "x": 80,
    "y": 80,
    "skin": "vector_default",
}


def load_prefs() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    if PREFS_PATH.exists():
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if isinstance(loaded, dict):
            data.update(loaded)
    try:
        data["scale"] = float(data.get("scale", 1.0))
    except (TypeError, ValueError):
        data["scale"] = 1.0
    try:
        data["x"] = int(data.get("x", 80))
        data["y"] = int(data.get("y", 80))
    except (TypeError, ValueError):
        data["x"], data["y"] = 80, 80
    data["skin"] = str(data.get("skin") or "vector_default")
    return data


def save_prefs(*, scale: float, x: int, y: int, skin: str | None = None) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    prev = load_prefs()
    payload = {
        "scale": round(float(scale), 4),
        "x": int(x),
        "y": int(y),
        "skin": skin if skin is not None else prev.get("skin", "vector_default"),
    }
    header = "# 悬浮窗状态（缩放/位置自动写入；skin 为当前皮肤 id）\n\n"
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(payload, f, allow_unicode=True, default_flow_style=False)


def clamp_pos(x: int, y: int, w: int = 200, h: int = 120) -> Tuple[int, int]:
    """把窗口左上角限制在可见屏幕内（至少露出一角）。"""
    try:
        from PyQt5.QtGui import QGuiApplication

        screens = QGuiApplication.screens()
        if not screens:
            return x, y
        # 若已落在某块屏内则不改；否则吸到主屏
        for scr in screens:
            g = scr.availableGeometry()
            if g.adjusted(-40, -40, 40, 40).contains(x, y):
                # 保证不完全拖出
                nx = min(max(x, g.left() - w + 80), g.right() - 40)
                ny = min(max(y, g.top() - h + 40), g.bottom() - 40)
                return int(nx), int(ny)
        g = screens[0].availableGeometry()
        return int(g.left() + 80), int(g.top() + 80)
    except Exception:
        return x, y
