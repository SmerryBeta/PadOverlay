"""应用根目录与打包资源旁路释放。

开发时 ROOT = 仓库根；PyInstaller 打包后 ROOT = exe 所在目录。
内嵌的默认 config/skins 在 BUNDLE（_MEIPASS）里；旁路缺失时拷到 ROOT，不覆盖已有文件。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_FROZEN = getattr(sys, "frozen", False)


def _resolve_root() -> Path:
    if _FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resolve_bundle() -> Path:
    if _FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


ROOT = _resolve_root()
BUNDLE = _resolve_bundle()

# 旁路默认资源：缺失则从包内拷出
_SIDECAR_DIRS = ("config", "skins")


def _copy_missing_tree(src: Path, dst: Path) -> int:
    """把 src 树中目标尚不存在的文件拷到 dst，返回新拷贝数量。"""
    if not src.is_dir():
        return 0
    n = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        # 跳过皮肤目录里可能残留的源图草稿
        if path.name.startswith("_source"):
            continue
        rel = path.relative_to(src)
        target = dst / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def ensure_sidecar_assets() -> None:
    """exe 旁没有 config/skins（或残缺）时，从内嵌资源补齐。"""
    for name in _SIDECAR_DIRS:
        src = BUNDLE / name
        dst = ROOT / name
        if not src.is_dir():
            continue
        _copy_missing_tree(src, dst)
