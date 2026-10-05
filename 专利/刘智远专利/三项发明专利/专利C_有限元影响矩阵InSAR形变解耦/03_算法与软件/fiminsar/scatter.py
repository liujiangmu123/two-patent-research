# -*- coding: utf-8 -*-
"""S4：散射体候选仿真（塔顶/横担端/塔腿角钢二面角/夹持式角反射器）、可见性与 PS–杆件节点概率关联。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ._tk import sar


@dataclass(frozen=True)
class Geometry:
    name: str
    wavelength: float
    incidence: float
    heading: float
    revisit: float
    hour: float          # 地方时
    offset_day: float = 0.0

    @property
    def los(self):
        return sar.los_vector(self.incidence, self.heading)


def geometries(kind: str = "FC1"):
    """升降轨几何。S1 取 towerkit.sar.SATS 参数（晨昏轨道约 06:30/18:30）；
    FC1 为复成一号式 C 波段，过境时刻按非晨昏轨道假设（10:30 升 / 14:30 降，仿真假设，非官方参数）。"""
    if kind == "S1":
        a, d = sar.SATS["S1_ASC"], sar.SATS["S1_DSC"]
        return [Geometry("S1_ASC", a.wavelength, a.incidence, a.heading, a.revisit, 18.3, 0.0),
                Geometry("S1_DSC", d.wavelength, d.incidence, d.heading, d.revisit, 6.3, 5.0)]
    if kind == "FC1":
        return [Geometry("FC1_ASC", 0.0556, 35.0, -12.0, 11.0, 10.5, 0.0),
                Geometry("FC1_DSC", 0.0556, 38.0, -168.0, 11.0, 14.5, 4.0)]
    raise KeyError(kind)


@dataclass
class Candidate:
    node: int
    kind: str            # peak | arm_tip | leg_dihedral | body_dihedral | CR
    facing: np.ndarray   # 散射朝向（水平单位向量；CR 为 None 表示双向）
    weight: float
    offset: np.ndarray   # 相位中心相对节点偏置 m
    sigma_mm: float      # 视线向相位噪声等效 mm


def candidates(model, with_cr: bool = False):
    g, X = model.g, model.m.X
    out = []
    lv = np.asarray(g.meta["levels"])
    for i, t in enumerate(g.ntype):
        p = X[i]
        if t == "peak_tip":
            out.append(Candidate(i, "peak", np.array([np.sign(p[0]), 0, 0.0]), 1.0, np.zeros(3), 1.6))
        elif t in ("arm_tip",):
            out.append(Candidate(i, "arm_tip", np.array([np.sign(p[0]), 0, 0.0]), 0.8, np.zeros(3), 1.8))
        elif t == "corner":
            f = np.array([np.sign(p[0]), np.sign(p[1]), 0.0]) / math.sqrt(2)
            if abs(p[2] - lv[1]) < 0.1:
                out.append(Candidate(i, "leg_dihedral", f, 1.0, np.zeros(3), 1.5))
            elif p[2] < lv[8] + 0.1:
                out.append(Candidate(i, "body_dihedral", f, 0.5, np.zeros(3), 2.0))
    if with_cr:
        for i, t in enumerate(g.ntype):
            p = X[i]
            if t == "corner" and abs(p[2] - lv[1]) < 0.1:
                f = np.array([np.sign(p[0]), np.sign(p[1]), 0.0]) / math.sqrt(2)
                rho = 0.35 * f + np.array([0, 0, -0.02])
                out.append(Candidate(i, "CR", None, 3.0, rho, 0.5))
    return out


def visible(c: Candidate, geom: Geometry) -> bool:
    if c.facing is None:
        return True
    lh = geom.los.copy(); lh[2] = 0; lh /= np.linalg.norm(lh)
    return float(c.facing @ lh) > 0.15


def select_ps(cands, geom: Geometry, n_ps: int, rng, persist: float = 0.85):
    """按可见性与散射强度抽取该几何下的持久散射体（索引列表）。CR 总入选。"""
    vis = [k for k, c in enumerate(cands) if visible(c, geom)]
    cr = [k for k in vis if cands[k].kind == "CR"]
    ps = [k for k in vis if cands[k].kind != "CR" and rng.random() < persist]
    w = np.array([cands[k].weight for k in ps], float)
    n = min(n_ps, len(ps))
    pick = list(rng.choice(ps, n, replace=False, p=w / w.sum())) if n > 0 else []
    return cr + [int(k) for k in pick]


def associate(meas_xyz: np.ndarray, cands, geom: Geometry, model, sigma=(1.0, 1.0, 1.2), p0: float = 0.6):
    """概率关联：p_kc ∝ w_c exp(-½ δᵀΣ⁻¹δ)，只在本几何可见候选中搜索；返回 (候选索引或 -1, 后验概率)。"""
    vis = [k for k, c in enumerate(cands) if visible(c, geom)]
    P = np.array([model.m.X[cands[k].node] + cands[k].offset for k in vis])
    w = np.array([cands[k].weight for k in vis])
    S = np.asarray(sigma, float)
    res, prob = [], []
    for q in np.atleast_2d(meas_xyz):
        d2 = np.sum(((P - q) / S) ** 2, 1)
        lk = w * np.exp(-0.5 * (d2 - d2.min()))
        pk = lk / lk.sum()
        j = int(np.argmax(pk))
        res.append(vis[j] if pk[j] >= p0 else -1); prob.append(float(pk[j]))
    return np.array(res), np.array(prob)
