# -*- coding: utf-8 -*-
"""荷载：自重、风荷载（GB 50009 / DL/T 5551 简化）、导地线挂点荷载、覆冰、Kaimal 脉动风时程。"""
from __future__ import annotations

import numpy as np

from .fem import FEModel

RHO_AIR = 1.25


def mu_z(z, terrain: str = "B"):
    """风压高度变化系数（GB 50009-2012 指数律，z<10 m 取 10 m 值）。"""
    alpha = {"A": 0.12, "B": 0.15, "C": 0.22, "D": 0.30}[terrain]
    zg = {"A": 300.0, "B": 350.0, "C": 450.0, "D": 550.0}[terrain]
    coef = {"A": 1.284, "B": 1.000, "C": 0.544, "D": 0.262}[terrain]
    z = np.clip(np.asarray(z, float), {"A": 5, "B": 10, "C": 15, "D": 30}[terrain], zg)
    return coef * (z / 10.0) ** (2 * alpha)


def wind_static(model: FEModel, w0: float = 350.0, direction=(0.0, 1.0, 0.0), terrain="B", mu_s: float = 1.3,
                beta_z: float = 1.0) -> np.ndarray:
    """杆件风荷载等效节点力（N）。w0 单位 Pa；力 = w0·μz·μs·βz·b·|n|·n，n 为风向在杆件法平面内的分量。"""
    ew = np.asarray(direction, float); ew /= np.linalg.norm(ew)
    F = np.zeros(model.ndof)
    X = model.X
    for e in range(len(model.L)):
        a, b = model.mi[e], model.mj[e]
        ex = model.R[e, 0]
        n = ew - (ew @ ex) * ex
        zm = 0.5 * (X[a, 2] + X[b, 2])
        q = w0 * float(mu_z(zm, terrain)) * mu_s * beta_z * model.p.b[e] * np.linalg.norm(n)
        f = q * n * model.L[e] / 2
        F[6 * a:6 * a + 3] += f; F[6 * b:6 * b + 3] += f
    return F


def point_loads(model: FEModel, loads: dict) -> np.ndarray:
    """{node: (Fx, Fy, Fz)} → 荷载向量。"""
    F = np.zeros(model.ndof)
    for nd, f in loads.items():
        F[6 * nd:6 * nd + 3] += np.asarray(f, float)
    return F


def conductor_loads(model: FEModel, vertical: float = 25e3, transverse: float = 8e3, longitudinal: float = 0.0,
                    earthwire_factor: float = 0.35, ice_factor: float = 1.0) -> np.ndarray:
    """导线（地线按比例）挂点等效集中力：竖向（重力，含绝缘子串）、横向（风）、纵向（不平衡张力）。"""
    loads = {}
    for a in model.g.meta.get("attach", []):
        k = earthwire_factor if a["kind"] == "earthwire" else 1.0
        loads[a["node"]] = (longitudinal * k, transverse * k, -vertical * k * ice_factor)
    return point_loads(model, loads)


def ice_mass(model: FEModel, thickness: float = 0.01, rho_ice: float = 900.0) -> dict:
    """杆件覆冰附加质量（按两肢外表面冰厚近似）→ {node: kg}。"""
    out = {}
    for e in range(len(model.L)):
        m = rho_ice * thickness * 2 * model.p.b[e] * model.L[e] * 2
        for nd in (model.mi[e], model.mj[e]):
            out[int(nd)] = out.get(int(nd), 0.0) + m / 2
    return out


# ---------------------------------------------------------------------- 脉动风（Kaimal 谱 + Davenport 相干）
def kaimal_psd(f, U, sigma, Lu):
    return 4 * sigma ** 2 * Lu / U / (1 + 6 * f * Lu / U) ** (5.0 / 3.0)


def wind_field(heights, U10: float = 10.0, duration: float = 600.0, dt: float = 0.05, terrain="B",
               coherence: float = 10.0, seed: int = 0, fmax: float = 10.0):
    """返回 (t, U_mean(z), u'(z,t))：谱表示法生成各高度纵向脉动风速，Davenport 竖向相干 exp(−C·f·Δz/Ū)。"""
    rng = np.random.default_rng(seed)
    z = np.asarray(heights, float)
    alpha = {"A": 0.12, "B": 0.15, "C": 0.22, "D": 0.30}[terrain]
    Uz = U10 * (np.maximum(z, 5.0) / 10.0) ** alpha
    Iu = {"A": 0.12, "B": 0.14, "C": 0.23, "D": 0.39}[terrain] * (np.maximum(z, 5.0) / 10.0) ** (-alpha)
    sig = Iu * Uz
    Lu = 100.0 * (np.maximum(z, 5.0) / 30.0) ** 0.5
    nt = int(round(duration / dt))
    t = np.arange(nt) * dt
    df = 1.0 / duration
    freqs = np.arange(1, int(fmax / df)) * df
    nz = len(z)
    Ubar = 0.5 * (Uz[:, None] + Uz[None, :])
    dz = np.abs(z[:, None] - z[None, :])
    spec = np.zeros((nz, nt), complex)
    for f in freqs:
        S = kaimal_psd(f, Uz, sig, Lu)
        coh = np.exp(-coherence * f * dz / Ubar)
        Cm = np.sqrt(np.outer(S, S)) * coh
        Lc = np.linalg.cholesky(Cm + 1e-12 * np.eye(nz))
        ph = np.exp(1j * rng.uniform(0, 2 * np.pi, nz))
        k = int(round(f / df))
        spec[:, k] = Lc @ ph * np.sqrt(2 * df) / 2
    u = np.fft.ifft(spec, axis=1).real * nt * 2
    return t, Uz, u


def buffeting_loads(model: FEModel, U10=10.0, duration=600.0, dt=0.05, direction=(0.0, 1.0, 0.0), n_levels=12,
                    mu_s=1.3, seed=0, terrain="B"):
    """准定常抖振力时程 F(t)=ρ·Ū(z)·u'(z,t)·μs·b·|n|·n·L/2（分层插值到节点）。返回 (t, F_t (nt, ndof))。"""
    ew = np.asarray(direction, float); ew /= np.linalg.norm(ew)
    zmax = float(model.X[:, 2].max())
    lev = np.linspace(2.0, zmax, n_levels)
    t, Uz, u = wind_field(lev, U10, duration, dt, terrain, seed=seed)
    nt = len(t)
    F = np.zeros((nt, model.ndof))
    X = model.X
    for e in range(len(model.L)):
        a, b = model.mi[e], model.mj[e]
        ex = model.R[e, 0]
        n = ew - (ew @ ex) * ex
        zm = 0.5 * (X[a, 2] + X[b, 2])
        k = int(np.clip(np.searchsorted(lev, zm), 1, n_levels - 1))
        wgt = (zm - lev[k - 1]) / (lev[k] - lev[k - 1])
        uu = (1 - wgt) * u[k - 1] + wgt * u[k]
        UU = (1 - wgt) * Uz[k - 1] + wgt * Uz[k]
        q = RHO_AIR * UU * uu * mu_s * model.p.b[e] * np.linalg.norm(n) * model.L[e] / 2
        f = np.outer(q, n)
        F[:, 6 * a:6 * a + 3] += f; F[:, 6 * b:6 * b + 3] += f
    return t, F
