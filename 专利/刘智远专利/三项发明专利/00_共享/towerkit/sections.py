# -*- coding: utf-8 -*-
"""GB/T 706 等边角钢截面库、钢材参数与 GB 50017 轴压稳定系数。

截面特性按两块矩形组合的精确几何计算（不计内圆角 r），与 GB/T 706-2016 表值相比，
面积偏小约 0.5%～2%（内圆角面积 0.215 r²），惯性矩偏差同量级；用于结构仿真足够，
需要精确表值时可在 ``ANGLES`` 中覆写。单位：m、m²、m⁴、kg/m。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# GB/T 706 常用等边角钢肢宽 b(mm) 与厚度 t(mm)
_SIZES = {
    40: [3, 4, 5], 45: [4, 5], 50: [4, 5, 6], 56: [4, 5, 6], 63: [5, 6, 8],
    70: [5, 6, 7, 8], 75: [5, 6, 7, 8, 10], 80: [6, 7, 8, 10], 90: [6, 7, 8, 10, 12],
    100: [6, 7, 8, 10, 12, 14, 16], 110: [7, 8, 10, 12, 14], 125: [8, 10, 12, 14],
    140: [10, 12, 14, 16], 160: [10, 12, 14, 16], 180: [12, 14, 16, 18],
    200: [14, 16, 18, 20, 24], 220: [16, 18, 20, 22, 24, 26], 250: [18, 20, 24, 26, 28, 30, 32, 35],
}
RHO_STEEL = 7850.0


@dataclass(frozen=True)
class Angle:
    name: str
    b: float      # 肢宽 m
    t: float      # 肢厚 m
    A: float      # 截面积 m²
    mass: float   # kg/m
    e: float      # 形心至肢背距离 m
    Ix: float     # 对平行于肢的形心轴惯性矩 m⁴
    Iu: float     # 强轴惯性矩 m⁴
    Iv: float     # 弱轴惯性矩 m⁴
    ix: float     # 平行轴回转半径 m
    iv: float     # 最小回转半径 m
    J: float      # 抗扭常数 m⁴

    @property
    def label(self) -> str:
        return self.name


def _angle(bmm: int, tmm: int) -> Angle:
    b, t = bmm / 1000.0, tmm / 1000.0
    # 矩形 1：x∈[0,b], y∈[0,t]；矩形 2：x∈[0,t], y∈[t,b]
    a1, a2 = b * t, t * (b - t)
    c1 = (b / 2, t / 2)
    c2 = (t / 2, t + (b - t) / 2)
    A = a1 + a2
    cx = (a1 * c1[0] + a2 * c2[0]) / A
    cy = (a1 * c1[1] + a2 * c2[1]) / A
    ix_ = b * t ** 3 / 12 + a1 * (c1[1] - cy) ** 2 + t * (b - t) ** 3 / 12 + a2 * (c2[1] - cy) ** 2
    iy_ = t * b ** 3 / 12 + a1 * (c1[0] - cx) ** 2 + (b - t) * t ** 3 / 12 + a2 * (c2[0] - cx) ** 2
    ixy = a1 * (c1[0] - cx) * (c1[1] - cy) + a2 * (c2[0] - cx) * (c2[1] - cy)
    mid = (ix_ + iy_) / 2
    rad = math.sqrt(((ix_ - iy_) / 2) ** 2 + ixy ** 2)
    iu, iv = mid + rad, mid - rad
    J = (b * t ** 3 + (b - t) * t ** 3) / 3
    return Angle(name=f"L{bmm}x{tmm}", b=b, t=t, A=A, mass=A * RHO_STEEL, e=cx, Ix=ix_, Iu=iu, Iv=iv,
                 ix=math.sqrt(ix_ / A), iv=math.sqrt(iv / A), J=J)


ANGLES: dict[str, Angle] = {}
for _b, _ts in _SIZES.items():
    for _t in _ts:
        _a = _angle(_b, _t)
        ANGLES[_a.name] = _a
#: 按截面积升序排列的规格名（离散优化的候选序列）
ANGLE_ORDER: list[str] = sorted(ANGLES, key=lambda k: (ANGLES[k].A, ANGLES[k].b))


def angle(name: str) -> Angle:
    """按名称取角钢，接受 'L125x10'、'L125×10'。"""
    key = name.replace("×", "x").replace("X", "x").strip()
    if not key.startswith("L"):
        key = "L" + key
    return ANGLES[key]


def lightest(pred, candidates=None) -> Angle:
    """返回满足谓词 pred(Angle)->bool 的最轻规格。"""
    for k in (candidates or ANGLE_ORDER):
        a = ANGLES[k]
        if pred(a):
            return a
    return ANGLES[ANGLE_ORDER[-1]]


def step(name: str, k: int) -> str:
    """在面积序列中向上(k>0)/向下(k<0)移动 k 档。"""
    i = ANGLE_ORDER.index(angle(name).name)
    return ANGLE_ORDER[max(0, min(len(ANGLE_ORDER) - 1, i + k))]


# ------------------------------------------------------------------ 钢材（GB 50017-2017，厚度 ≤16 mm 设计值）
@dataclass(frozen=True)
class Steel:
    name: str
    E: float = 2.06e11
    nu: float = 0.30
    rho: float = RHO_STEEL
    fy: float = 355e6
    f: float = 305e6
    alpha: float = 1.2e-5

    @property
    def G(self) -> float:
        return self.E / (2 * (1 + self.nu))


STEELS = {
    "Q235": Steel("Q235", fy=235e6, f=215e6),
    "Q355": Steel("Q355", fy=355e6, f=305e6),
    "Q420": Steel("Q420", fy=420e6, f=375e6),
}


def steel(name: str) -> Steel:
    return STEELS[name]


# ------------------------------------------------------------------ GB 50017 轴心受压稳定系数（b 类截面）
def phi_b(lam: float, fy: float = 235e6, E: float = 2.06e11) -> float:
    """GB 50017-2017 附录 D 公式：b 类截面，α1=0.65, α2=0.965, α3=0.300。"""
    lam_n = lam / math.pi * math.sqrt(fy / E)
    if lam_n <= 0.215:
        return 1.0 - 0.65 * lam_n ** 2
    a2, a3 = 0.965, 0.300
    s = a2 + a3 * lam_n + lam_n ** 2
    return (s - math.sqrt(s * s - 4 * lam_n ** 2)) / (2 * lam_n ** 2)


#: DL/T 5486 杆件允许长细比（受压主材 150、受压斜材 200、辅助材 250、受拉材 400）
LAMBDA_LIMIT = {"main": 150.0, "diagonal": 200.0, "auxiliary": 250.0, "tension": 400.0}
