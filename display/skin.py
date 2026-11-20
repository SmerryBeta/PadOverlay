"""皮肤加载：skins/<id>/skin.yml + layout + 图片。"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import yaml
from PyQt5.QtGui import QImage, qAlpha, qBlue, qGreen, qRed

from app_paths import ROOT

SKINS_DIR = ROOT / "skins"


def _load_rgba_masked(path: Path) -> Optional[QImage]:
    """加载 PNG：A=0 清脏 RGB；再 Format_ARGB32_Premultiplied（RGB*=A/255）。"""
    img = QImage(str(path))
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    for y in range(h):
        for x in range(w):
            c = img.pixel(x, y)
            if qAlpha(c) == 0 and (qRed(c) | qGreen(c) | qBlue(c)) != 0:
                img.setPixel(x, y, 0)
    # Qt 预乘 = 用 alpha 掩码乘颜色通道，软边合成才正确
    return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)

_lock = Lock()
_current_id: Optional[str] = None
_cache: Optional["Skin"] = None


class Skin:
    def __init__(self, skin_id: str, folder: Path) -> None:
        self.id = skin_id
        self.folder = folder
        meta_path = folder / "skin.yml"
        meta: Dict = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
        self.name = str(meta.get("name") or skin_id)
        self.mode = str(meta.get("mode") or "vector").lower()
        self.layout_path = folder / "layout.yml"
        self.base_name = str(meta.get("base") or "base.png")
        self.active_dir = folder / str(meta.get("active_dir") or "active")
        self.inactive_dir = folder / str(meta.get("inactive_dir") or "inactive")
        self._base: Optional[QImage] = None
        self._active: Dict[str, QImage] = {}
        self._inactive: Dict[str, QImage] = {}
        if self.mode == "image":
            self._load_images()

    def _load_images(self) -> None:
        base_path = self.folder / self.base_name
        if base_path.exists():
            self._base = _load_rgba_masked(base_path)
        self._active = self._load_dir(self.active_dir)
        self._inactive = self._load_dir(self.inactive_dir)

    @staticmethod
    def _load_dir(path: Path) -> Dict[str, QImage]:
        out: Dict[str, QImage] = {}
        if not path.is_dir():
            return out
        for p in path.iterdir():
            if p.suffix.lower() not in (".png", ".webp", ".jpg", ".jpeg"):
                continue
            if p.name.startswith("_"):
                continue
            img = _load_rgba_masked(p)
            if img is None:
                continue
            out[p.stem.lower()] = img
        return out

    @property
    def base(self) -> Optional[QImage]:
        return self._base

    def active_img(self, part: str) -> Optional[QImage]:
        return self._active.get(part.lower())

    def inactive_img(self, part: str) -> Optional[QImage]:
        return self._inactive.get(part.lower())

    def reload_images(self) -> None:
        if self.mode == "image":
            self._base = None
            self._active.clear()
            self._inactive.clear()
            self._load_images()


def list_skins() -> List[tuple[str, str]]:
    """返回 [(id, display_name), ...]，跳过 _ 开头。"""
    result: List[tuple[str, str]] = []
    if not SKINS_DIR.is_dir():
        return result
    for p in sorted(SKINS_DIR.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if not (p / "skin.yml").exists():
            continue
        try:
            sk = Skin(p.name, p)
            result.append((sk.id, sk.name))
        except Exception:
            result.append((p.name, p.name))
    return result


def _read_skin_id_from_prefs() -> str:
    prefs = ROOT / "config" / "window.yml"
    if prefs.exists():
        with open(prefs, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sid = str(data.get("skin") or "vector_default")
        if (SKINS_DIR / sid / "skin.yml").exists():
            return sid
    return "vector_default"


def get_skin(force_reload: bool = False) -> Skin:
    global _cache, _current_id
    with _lock:
        sid = _read_skin_id_from_prefs() if _current_id is None else _current_id
        if force_reload or _cache is None or _cache.id != sid:
            folder = SKINS_DIR / sid
            if not (folder / "skin.yml").exists():
                folder = SKINS_DIR / "vector_default"
                sid = "vector_default"
            _cache = Skin(sid, folder)
            _current_id = sid
        return _cache


def set_skin(skin_id: str) -> Skin:
    global _cache, _current_id
    folder = SKINS_DIR / skin_id
    if not (folder / "skin.yml").exists():
        raise FileNotFoundError(f"皮肤不存在: {skin_id}")
    with _lock:
        _current_id = skin_id
        _cache = Skin(skin_id, folder)
    # 写入 prefs（保留缩放位置）
    from display.window_prefs import load_prefs, save_prefs

    prefs = load_prefs()
    save_prefs(scale=float(prefs["scale"]), x=int(prefs["x"]), y=int(prefs["y"]), skin=skin_id)
    # 切换皮肤后重载布局缓存
    from display.layout import get_layout

    get_layout(force_reload=True)
    return _cache


def active_skin_dir() -> Path:
    return get_skin().folder
