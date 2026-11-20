"""手柄可视化状态：部件引用计数 + 摇杆平滑插值。"""
from __future__ import annotations

import math
from threading import Lock
from typing import Dict, Iterable, List, Optional, Set, Tuple

# 越大跟手越快；约 10~16 比较丝滑（略降以减轻右摇杆肉眼抖动）
STICK_SMOOTH_SPEED = 10.0
STICK_SNAP_EPS = 0.004
# 鼠标停下后右摇杆回中速度（过快会和下一帧输入对拉成「震动」）
RS_MOUSE_DECAY = 6.5
RS_MOUSE_IDLE_EPS = 0.04
# 新鼠标样本混入比例；过大易抖，过小发黏
RS_MOUSE_BLEND = 0.42


class PadState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._refs: Dict[str, int] = {}
        # 平滑后的摇杆位置（显示用）
        self._smooth: Dict[str, List[float]] = {
            "ls": [0.0, 0.0],
            "rs": [0.0, 0.0],
        }
        # 鼠标位移驱动右摇杆（覆盖按键目标；静止后衰减清除）
        self._rs_mouse: Optional[List[float]] = None

    def press(self, parts: Iterable[str]) -> None:
        with self._lock:
            for part in parts:
                self._refs[part] = self._refs.get(part, 0) + 1

    def release(self, parts: Iterable[str]) -> None:
        with self._lock:
            for part in parts:
                cur = self._refs.get(part, 0)
                if cur <= 1:
                    self._refs.pop(part, None)
                else:
                    self._refs[part] = cur - 1

    def clear(self) -> None:
        with self._lock:
            self._refs.clear()
            self._rs_mouse = None
            for v in self._smooth.values():
                v[0] = 0.0
                v[1] = 0.0

    def set_rs_mouse(self, x: Optional[float], y: Optional[float] = None) -> None:
        """
        鼠标驱动右摇杆。传 (None, None) 或 x=None 清除覆盖。
        坐标系：x 右为正，y 下为正（与屏幕一致）。
        用 EMA 混入，避免多路小抖动把摇杆抽成震动。
        """
        with self._lock:
            if x is None:
                self._rs_mouse = None
                return
            nx = max(-1.0, min(1.0, float(x)))
            ny = max(-1.0, min(1.0, 0.0 if y is None else float(y)))
            if self._rs_mouse is None:
                self._rs_mouse = [nx, ny]
                return
            a = RS_MOUSE_BLEND
            self._rs_mouse[0] = self._rs_mouse[0] * (1.0 - a) + nx * a
            self._rs_mouse[1] = self._rs_mouse[1] * (1.0 - a) + ny * a
            # 同向加速：略抬一点跟手，但不瞬切满偏
            cx, cy = self._rs_mouse
            if nx * cx > 0 and abs(nx) > abs(cx):
                self._rs_mouse[0] = cx * 0.65 + nx * 0.35
            if ny * cy > 0 and abs(ny) > abs(cy):
                self._rs_mouse[1] = cy * 0.65 + ny * 0.35

    def active(self) -> Set[str]:
        with self._lock:
            out = {k for k, v in self._refs.items() if v > 0}
            # 鼠标推右摇杆时补上方向部件，便于摇杆高亮
            if self._rs_mouse is not None:
                mx, my = self._rs_mouse
                if abs(mx) >= 0.28:
                    out.add("rs_left" if mx < 0 else "rs_right")
                if abs(my) >= 0.28:
                    out.add("rs_up" if my < 0 else "rs_down")
            return out

    def is_on(self, part: str) -> bool:
        with self._lock:
            return self._refs.get(part, 0) > 0

    def stick_target(self, prefix: str) -> Tuple[float, float]:
        """按键/鼠标目标位置。"""
        if prefix == "rs":
            with self._lock:
                if self._rs_mouse is not None:
                    return self._rs_mouse[0], self._rs_mouse[1]
        dx = dy = 0.0
        if self.is_on(f"{prefix}_left"):
            dx -= 1.0
        if self.is_on(f"{prefix}_right"):
            dx += 1.0
        if self.is_on(f"{prefix}_up"):
            dy -= 1.0
        if self.is_on(f"{prefix}_down"):
            dy += 1.0
        length = math.hypot(dx, dy)
        if length > 1.0:
            dx /= length
            dy /= length
        return dx, dy

    def stick_offset(self, prefix: str) -> Tuple[float, float]:
        """显示用平滑位置。"""
        with self._lock:
            v = self._smooth.get(prefix, [0.0, 0.0])
            return v[0], v[1]

    def tick_smooth(self, dt: float = 1.0 / 30.0, speed: float = STICK_SMOOTH_SPEED) -> bool:
        """
        每帧把摇杆从当前位置插值到按键/鼠标目标。
        返回是否仍在运动（需要继续重绘）。
        """
        # 指数趋近，帧率变化时手感更稳
        dt = max(dt, 1e-4)
        alpha = 1.0 - math.exp(-speed * dt)
        decay = math.exp(-RS_MOUSE_DECAY * dt)
        moved = False
        with self._lock:
            # 鼠标停下后右摇杆回中，清掉覆盖以便 Q/E 生效
            if self._rs_mouse is not None:
                self._rs_mouse[0] *= decay
                self._rs_mouse[1] *= decay
                if (
                    abs(self._rs_mouse[0]) < RS_MOUSE_IDLE_EPS
                    and abs(self._rs_mouse[1]) < RS_MOUSE_IDLE_EPS
                ):
                    self._rs_mouse = None
                else:
                    moved = True

            for prefix in ("ls", "rs"):
                if prefix == "rs" and self._rs_mouse is not None:
                    tx, ty = self._rs_mouse[0], self._rs_mouse[1]
                else:
                    tx = ty = 0.0
                    if self._refs.get(f"{prefix}_left", 0) > 0:
                        tx -= 1.0
                    if self._refs.get(f"{prefix}_right", 0) > 0:
                        tx += 1.0
                    if self._refs.get(f"{prefix}_up", 0) > 0:
                        ty -= 1.0
                    if self._refs.get(f"{prefix}_down", 0) > 0:
                        ty += 1.0
                    length = math.hypot(tx, ty)
                    if length > 1.0:
                        tx /= length
                        ty /= length

                cur = self._smooth[prefix]
                nx = cur[0] + (tx - cur[0]) * alpha
                ny = cur[1] + (ty - cur[1]) * alpha
                if abs(nx - tx) < STICK_SNAP_EPS:
                    nx = tx
                if abs(ny - ty) < STICK_SNAP_EPS:
                    ny = ty
                if abs(nx - cur[0]) > 1e-5 or abs(ny - cur[1]) > 1e-5:
                    moved = True
                cur[0], cur[1] = nx, ny
        return moved
