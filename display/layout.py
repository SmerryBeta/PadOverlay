"""手柄布局：YAML 读写，供绘制 / 热区 / 拖拽布置使用。"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parent.parent
# 兼容旧路径；优先使用当前皮肤目录下的 layout.yml
LEGACY_LAYOUT = ROOT / "config" / "layout.yml"

_lock = Lock()
_cache: Optional["ControllerLayout"] = None


def resolve_layout_path() -> Path:
    try:
        from display.skin import active_skin_dir

        skin_lay = active_skin_dir() / "layout.yml"
        if skin_lay.exists():
            return skin_lay
    except Exception:
        pass
    return LEGACY_LAYOUT


def default_layout_dict() -> Dict[str, Any]:
    return {
        "canvas": {
            "w": 520,
            "h": 300,
            # 底板相对画布：左上角偏移 + 缩放 + 旋转（度，绕底板中心）
            "base_x": 0.0,
            "base_y": 0.0,
            "base_scale": 1.0,
            "base_rot": 0.0,
        },
        "parts": {
            "lt": {"type": "bumper", "x": 118, "y": 12, "w": 62, "h": 20, "label": "LT"},
            "rt": {"type": "bumper", "x": 340, "y": 12, "w": 62, "h": 20, "label": "RT"},
            "lb": {"type": "bumper", "x": 168, "y": 48, "w": 62, "h": 16, "label": "LB"},
            "rb": {"type": "bumper", "x": 290, "y": 48, "w": 62, "h": 16, "label": "RB"},
            "btn_y": {"type": "face", "x": 352, "y": 104, "r": 13, "label": "Y"},
            "btn_x": {"type": "face", "x": 326, "y": 130, "r": 13, "label": "X"},
            "btn_b": {"type": "face", "x": 378, "y": 130, "r": 13, "label": "B"},
            "btn_a": {"type": "face", "x": 352, "y": 156, "r": 13, "label": "A"},
            "btn_view": {"type": "small", "x": 238, "y": 152, "r": 8},
            "btn_menu": {"type": "small", "x": 282, "y": 152, "r": 8},
            "guide": {"type": "guide", "x": 260, "y": 178, "r": 11},
            "ls": {"type": "stick", "x": 168, "y": 130, "r": 30},
            "rs": {"type": "stick", "x": 352, "y": 210, "r": 30},
            "dpad": {"type": "dpad", "x": 168, "y": 210, "arm": 20},
        },
    }


class ControllerLayout:
    def __init__(self, data: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_LAYOUT
        self._data: Dict[str, Any] = data or default_layout_dict()

    @property
    def canvas(self) -> Dict[str, Any]:
        return self._data.setdefault("canvas", {})

    @property
    def canvas_w(self) -> int:
        return int(self.canvas.get("w", 520))

    @property
    def canvas_h(self) -> int:
        return int(self.canvas.get("h", 300))

    @property
    def base_x(self) -> float:
        return float(self.canvas.get("base_x", 0.0) or 0.0)

    @property
    def base_y(self) -> float:
        return float(self.canvas.get("base_y", 0.0) or 0.0)

    @property
    def base_scale(self) -> float:
        try:
            return max(0.15, float(self.canvas.get("base_scale", 1.0) or 1.0))
        except (TypeError, ValueError):
            return 1.0

    @property
    def base_rot(self) -> float:
        try:
            return float(self.canvas.get("base_rot", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def parts(self) -> Dict[str, Dict[str, Any]]:
        return self._data.setdefault("parts", {})

    def part(self, name: str) -> Optional[Dict[str, Any]]:
        return self.parts.get(name)

    def reload(self) -> None:
        if not self.path.exists():
            self._data = default_layout_dict()
            return
        with open(self.path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        base = default_layout_dict()
        # 合并缺省，避免旧文件缺键
        base["canvas"].update(loaded.get("canvas") or {})
        parts = base["parts"]
        for k, v in (loaded.get("parts") or {}).items():
            if k in parts and isinstance(v, dict):
                parts[k] = {**parts[k], **v}
            elif isinstance(v, dict):
                parts[k] = v
        self._data = base

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "# 手柄按键布局 — 可用设置页「布置布局」拖拽保存，也可手改本文件\n"
            "# 改完后点设置里「重载布局」或重启生效\n\n"
        )
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.safe_dump(
                self._data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

    def move_part(self, name: str, x: float, y: float) -> None:
        """把部件锚点移到 (x,y)。bumper 用左上角；其余用中心。"""
        p = self.parts.get(name)
        if not p:
            return
        p["x"] = round(x, 1)
        p["y"] = round(y, 1)

    def scale_part(self, name: str, factor: float) -> float:
        """相对缩放部件图标，写入 parts[name].scale，返回新 scale。"""
        p = self.parts.get(name)
        if not p:
            return 1.0
        cur = float(p.get("scale", 1.0) or 1.0)
        cur = max(0.2, min(3.0, cur * float(factor)))
        p["scale"] = round(cur, 3)
        return cur

    def rotate_part(self, name: str, delta_deg: float) -> float:
        """相对旋转部件（度），写入 parts[name].rot。"""
        p = self.parts.get(name)
        if not p:
            return 0.0
        cur = float(p.get("rot", 0.0) or 0.0) + float(delta_deg)
        # 归一到 (-180, 180]
        while cur > 180:
            cur -= 360
        while cur <= -180:
            cur += 360
        p["rot"] = round(cur, 1)
        return cur

    def move_base(self, x: float, y: float) -> None:
        self.canvas["base_x"] = round(x, 1)
        self.canvas["base_y"] = round(y, 1)

    def scale_base(self, factor: float) -> float:
        cur = self.base_scale * float(factor)
        cur = max(0.2, min(3.0, cur))
        self.canvas["base_scale"] = round(cur, 3)
        return cur

    def rotate_base(self, delta_deg: float) -> float:
        cur = self.base_rot + float(delta_deg)
        while cur > 180:
            cur -= 360
        while cur <= -180:
            cur += 360
        self.canvas["base_rot"] = round(cur, 1)
        return cur

    def snapshot(self) -> Dict[str, Any]:
        return deepcopy(self._data)

    def restore(self, data: Dict[str, Any]) -> None:
        self._data = deepcopy(data)


def get_layout(force_reload: bool = False) -> ControllerLayout:
    global _cache
    with _lock:
        path = resolve_layout_path()
        if _cache is None or force_reload or _cache.path != path:
            lay = ControllerLayout(path=path)
            lay.reload()
            _cache = lay
        return _cache


def save_layout(layout: ControllerLayout) -> None:
    layout.path = resolve_layout_path()
    layout.save()
    with _lock:
        global _cache
        _cache = layout


# 可拖拽布置的部件（不含 guide）
DRAGGABLE_PARTS: List[str] = [
    "lt", "lb", "rt", "rb",
    "btn_y", "btn_x", "btn_b", "btn_a",
    "btn_view", "btn_menu",
    "ls", "rs", "dpad",
]


def part_scale(part: Dict[str, Any]) -> float:
    try:
        return max(0.05, float(part.get("scale", 1.0) or 1.0))
    except (TypeError, ValueError):
        return 1.0


def part_rot(part: Dict[str, Any]) -> float:
    try:
        return float(part.get("rot", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def part_metrics(part: Dict[str, Any]) -> Dict[str, float]:
    """带 scale 的绘制/命中尺寸（不改写原 dict）。"""
    s = part_scale(part)
    t = part.get("type")
    out: Dict[str, float] = {
        "x": float(part["x"]),
        "y": float(part["y"]),
        "scale": s,
        "rot": part_rot(part),
    }
    if t == "bumper":
        out["w"] = float(part["w"]) * s
        out["h"] = float(part["h"]) * s
    elif t == "dpad":
        out["arm"] = float(part.get("arm", 20)) * s
    else:
        out["r"] = float(part.get("r", 16)) * s
    return out


def part_anchor(part: Dict[str, Any]) -> Tuple[float, float]:
    """部件变换中心：bumper 为矩形中心，其余为锚点中心。"""
    m = part_metrics(part)
    t = part.get("type")
    if t == "bumper":
        return m["x"] + m["w"] / 2.0, m["y"] + m["h"] / 2.0
    return m["x"], m["y"]
