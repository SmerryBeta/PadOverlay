"""YAML 映射读写：物理键 ↔ 手柄部件。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEYMAP = ROOT / "config" / "keymap.yml"

# 设置界面可点选的部件（显示名）
PART_LABELS: Dict[str, str] = {
    "btn_a": "A · 脚踢",
    "btn_b": "B · 头槌",
    "btn_x": "X · 挥拳/投掷",
    "btn_y": "Y · 跳跃",
    "btn_menu": "Menu · 积分板",
    "btn_view": "View",
    "lt": "LT · 冲刺",
    "rt": "RT · 抓取",
    "lb": "LB · 钓鱼轮盘",
    "rb": "RB",
    "ls_up": "左摇杆 ↑",
    "ls_down": "左摇杆 ↓",
    "ls_left": "左摇杆 ←",
    "ls_right": "左摇杆 →",
    "rs_up": "右摇杆 ↑",
    "rs_down": "右摇杆 ↓",
    "rs_left": "右摇杆 ←",
    "rs_right": "右摇杆 →",
    "dpad_up": "十字 ↑",
    "dpad_down": "十字 ↓",
    "dpad_left": "十字 ← · 动作轮盘",
    "dpad_right": "十字 → · 表情轮盘",
}


class KeyMapper:
    """内存中的 keymap；可保存/加载 YAML。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_KEYMAP
        self._keys: Dict[str, List[str]] = {}
        self.reload()

    @property
    def keys(self) -> Dict[str, List[str]]:
        return self._keys

    def reload(self) -> Dict[str, List[str]]:
        if not self.path.exists():
            self._keys = {}
            return self._keys
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        raw = data.get("keys") or {}
        out: Dict[str, List[str]] = {}
        for key, parts in raw.items():
            name = str(key).strip().lower()
            if isinstance(parts, str):
                parts = [parts]
            out[name] = [str(p) for p in parts]
        self._keys = out
        return self._keys

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 稳定排序，便于 diff
        ordered = {k: self._keys[k] for k in sorted(self._keys.keys())}
        payload = {
            "keys": ordered,
        }
        header = (
            "# PadOverlay 键位映射（物理键 → 手柄部件）\n"
            "# 由设置界面写入；也可手改后重启或点保存热加载。\n\n"
        )
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.safe_dump(
                payload,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

    def parts_for_key(self, key: str) -> List[str]:
        return list(self._keys.get(key.lower(), []))

    def keys_for_part(self, part: str) -> List[str]:
        return [k for k, parts in self._keys.items() if part in parts]

    def bind_key_to_part(self, key: str, part: str, exclusive_part: bool = True) -> None:
        """
        将物理键绑定到部件。
        exclusive_part=True 时先从所有键上移除该部件，再把部件加到该键。
        """
        key = key.strip().lower()
        if exclusive_part:
            for k in list(self._keys.keys()):
                if part in self._keys[k]:
                    self._keys[k] = [p for p in self._keys[k] if p != part]
                    if not self._keys[k]:
                        del self._keys[k]
        parts = self._keys.setdefault(key, [])
        if part not in parts:
            parts.append(part)

    def clear_part(self, part: str) -> None:
        for k in list(self._keys.keys()):
            if part in self._keys[k]:
                self._keys[k] = [p for p in self._keys[k] if p != part]
                if not self._keys[k]:
                    del self._keys[k]

    def snapshot(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._keys.items()}
