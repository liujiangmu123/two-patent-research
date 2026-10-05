# -*- coding: utf-8 -*-
"""S3：太阳位置 + 桁架几何射线投射的日照遮挡热场，及逐景热基函数 ψ1（均匀）、ψ2（日照分布）。"""
from __future__ import annotations

import math

import numpy as np


def sun_vector(day_of_year: float, local_solar_hour: float, lat_deg: float = 29.6) -> np.ndarray:
    """ENU 太阳方向单位向量（地方太阳时）。太阳在地平线下时 z<0。"""
    dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + day_of_year) / 365.0)
    h = math.radians(15.0 * (local_solar_hour - 12.0))
    lat = math.radians(lat_deg)
    sin_el = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(h)
    el = math.asin(max(-1.0, min(1.0, sin_el)))
    cos_az = (math.sin(dec) - math.sin(el) * math.sin(lat)) / max(1e-9, math.cos(el) * math.cos(lat))
    az = math.acos(max(-1.0, min(1.0, cos_az)))
    if h > 0:
        az = 2 * math.pi - az                       # 下午：方位角在西
    return np.array([math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)])


def irradiance(sun: np.ndarray) -> float:
    """晴空直射辐照 W/m²（简单大气质量模型），太阳在地平线下为 0。"""
    s = sun[2]
    if s <= 0.02:
        return 0.0
    return 1361.0 * 0.7 ** ((1.0 / s) ** 0.678)


def angle_leg_normals(model) -> np.ndarray:
    """每根角钢两肢外法向 (M,2,3)。主材按所在塔腿角点外侧取（±x、±y），其余取局部轴 ±y/±z 组合。"""
    g, m = model.g, model.m
    X = m.X
    N = np.zeros((g.n_members, 2, 3))
    for e in range(g.n_members):
        mid = 0.5 * (X[m.mi[e]] + X[m.mj[e]])
        if g.cat[e] == "main" and g.part[e] == "body":
            sx, sy = np.sign(mid[0]) or 1.0, np.sign(mid[1]) or 1.0
            N[e, 0] = [sx, 0, 0]; N[e, 1] = [0, sy, 0]
        else:
            ey, ez = m.R[e, 1], m.R[e, 2]
            N[e, 0] = ey; N[e, 1] = ez
    return N


def _seg_seg_dist(p0, d0, q0, q1):
    """射线段 p0+s d0 (s∈[0,1]) 与一组线段 q0→q1 的最短距离（向量化，近似夹取）。"""
    u = d0[None, :]
    v = q1 - q0
    w = p0[None, :] - q0
    a = np.sum(u * u, 1); b = np.sum(u * v, 1); c = np.sum(v * v, 1)
    d = np.sum(u * w, 1); e = np.sum(v * w, 1)
    den = a * c - b * b
    s = np.where(den > 1e-12, (b * e - c * d) / np.maximum(den, 1e-12), 0.0)
    s = np.clip(s, 0, 1)
    t = np.clip((b * s + e) / np.maximum(c, 1e-12), 0, 1)
    s = np.clip((b * t - d) / np.maximum(a, 1e-12), 0, 1)
    diff = w + s[:, None] * u - t[:, None] * v
    return np.linalg.norm(diff, axis=1)


def shadow_fraction(model, sun: np.ndarray, n_samp: int = 3, ray_len: float = 90.0) -> np.ndarray:
    """逐杆件受照比例 η∈[0,1]：杆上 n_samp 个采样点沿太阳方向射线，被其它杆件（以肢宽为半径）遮挡即记阴影。"""
    m = model.m
    X = m.X
    P0, P1 = X[m.mi], X[m.mj]
    width = m.p.b
    M = len(P0)
    eta = np.ones(M)
    if sun[2] <= 0.02:
        return np.zeros(M)
    d0 = sun * ray_len
    for e in range(M):
        lit = 0
        for s in (np.arange(n_samp) + 0.5) / n_samp:
            p = P0[e] + s * (P1[e] - P0[e]) + 0.05 * sun
            dist = _seg_seg_dist(p, d0, P0, P1)
            dist[e] = np.inf
            lit += not np.any(dist < 0.5 * (width + width[e]) * 0.7)
        eta[e] = lit / n_samp
    return eta


def solar_term(model, sun: np.ndarray, normals=None, eta=None) -> np.ndarray:
    """ψ2：单位辐照（1 kW/m²）下的逐杆件日照分量 Σ_a ½ η max(0, n_a·s)。"""
    normals = angle_leg_normals(model) if normals is None else normals
    eta = shadow_fraction(model, sun) if eta is None else eta
    cosv = np.clip(np.einsum("mac,c->ma", normals, sun), 0, None)
    # 肢面法向可正可反（角钢两侧均可受照），取外侧；非主材两侧取大者
    cosv2 = np.clip(np.einsum("mac,c->ma", -normals, sun), 0, None)
    is_main = np.array([c == "main" and p == "body" for c, p in zip(model.g.cat, model.g.part)])
    cosv = np.where(is_main[:, None], cosv, np.maximum(cosv, cosv2))
    return eta * 0.5 * cosv.sum(1)


def air_temperature(day: float, hour: float) -> float:
    """季节 + 日变化气温（℃），重庆近似。"""
    seasonal = 18.0 - 10.0 * math.cos(2 * math.pi * (day - 15) / 365.0)
    diurnal = 4.5 * math.cos(2 * math.pi * (hour - 15.0) / 24.0)
    return seasonal + diurnal
