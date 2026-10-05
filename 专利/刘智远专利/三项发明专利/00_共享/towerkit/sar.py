# -*- coding: utf-8 -*-
"""SAR 几何与 InSAR 观测仿真：卫星参数、视线向（LOS）、角反射器 RCS、相位噪声、大气延迟。

LOS 单位向量定义为“地面点指向卫星”（ENU），形变朝向卫星为正。右视成像，航向角为飞行方向自北顺时针。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Sat:
    name: str
    wavelength: float      # m
    incidence: float       # °
    heading: float         # ° 飞行方向（自北顺时针）
    revisit: float         # d
    res_rg: float          # 斜距分辨率 m
    res_az: float          # 方位分辨率 m


SATS = {
    "S1_ASC": Sat("Sentinel-1 升轨", 0.055465, 39.0, -12.0, 12.0, 2.3, 14.1),
    "S1_DSC": Sat("Sentinel-1 降轨", 0.055465, 39.0, -168.0, 12.0, 2.3, 14.1),
    "LT1_ASC": Sat("陆探一号 升轨", 0.2384, 34.0, -10.0, 8.0, 1.7, 3.0),
    "LT1_DSC": Sat("陆探一号 降轨", 0.2384, 34.0, -170.0, 8.0, 1.7, 3.0),
    "TSX_ASC": Sat("TerraSAR-X 升轨", 0.031, 37.0, -10.0, 11.0, 1.2, 3.3),
    "TSX_DSC": Sat("TerraSAR-X 降轨", 0.031, 37.0, -170.0, 11.0, 1.2, 3.3),
}


def los_vector(incidence_deg: float, heading_deg: float) -> np.ndarray:
    th = math.radians(incidence_deg)
    look = math.radians(heading_deg + 90.0)          # 右视：视向方位 = 航向 + 90°
    # 卫星→地面的水平方向 (sin look, cos look)（东、北），LOS 取反并加竖直分量
    return np.array([-math.sin(th) * math.sin(look), -math.sin(th) * math.cos(look), math.cos(th)])


def project(disp_enu: np.ndarray, los: np.ndarray) -> np.ndarray:
    return np.asarray(disp_enu) @ los


def disp_to_phase(d, wavelength):
    return -4 * np.pi * np.asarray(d) / wavelength


def phase_to_disp(ph, wavelength):
    return -np.asarray(ph) * wavelength / (4 * np.pi)


def rcs_trihedral_triangular(a: float, wavelength: float) -> float:
    """三角形三面角反射器峰值 RCS（m²），a 为直角边长。"""
    return 4 * np.pi * a ** 4 / (3 * wavelength ** 2)


def rcs_trihedral_square(a: float, wavelength: float) -> float:
    return 12 * np.pi * a ** 4 / wavelength ** 2


def db(x):
    return 10 * np.log10(x)


def scr_phase_std(rcs: float, sigma0_db: float, res_rg: float, res_az: float, incidence_deg: float) -> float:
    """信杂比 → 相位标准差（rad）：σφ ≈ 1/√(2·SCR)。杂波 = σ0 · 地距像元面积。"""
    area = res_rg / math.sin(math.radians(incidence_deg)) * res_az
    clutter = 10 ** (sigma0_db / 10) * area
    scr = rcs / clutter
    return 1 / math.sqrt(2 * scr)


def acquisition_times(start_day: float, n: int, revisit: float, hour: float, offset_day: float = 0.0):
    """返回成像时刻（日序，含当地时刻小数）。"""
    return start_day + offset_day + np.arange(n) * revisit + hour / 24.0


def atmosphere(n_epochs: int, n_points: int, heights: np.ndarray, sigma_common: float = 0.004,
               k_strat: float = 3e-6, seed: int = 0):
    """大气延迟：各期公共项（同塔点相同，差分后抵消）+ 分层项（随高度，系数逐期随机）。返回 (n_epochs, n_points) m。"""
    rng = np.random.default_rng(seed)
    common = rng.normal(0, sigma_common, (n_epochs, 1))
    ks = rng.normal(0, k_strat, (n_epochs, 1))
    return common + ks * np.asarray(heights)[None, :]
