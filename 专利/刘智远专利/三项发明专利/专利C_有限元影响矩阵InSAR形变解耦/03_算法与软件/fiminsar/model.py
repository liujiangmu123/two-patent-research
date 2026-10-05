# -*- coding: utf-8 -*-
"""S1/S2：杆件级桁架有限元模型与单位工况影响矩阵（基础位移 G_b、热基 G_T、风 G_w）。

影响矩阵列保存全自由度位移（含节点转角），以便任意节点/夹持式角反射器偏置点取值。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._tk import build_tower, fem, loads

T_REF = 20.0           # 无应力参考温度 ℃
W_UNIT = 100.0         # 单位风工况基本风压 Pa


@dataclass
class TowerModel:
    g: object
    m: object
    base: list
    Gb: np.ndarray                 # (ndof, 12) 列序：腿0 x,y,z, 腿1 x,y,z ...
    GT1: np.ndarray                # (ndof,) 全塔均匀 1 ℃
    Gw: np.ndarray                 # (ndof, 2) x/y 向单位风压
    H: float
    _cache: dict = field(default_factory=dict)

    @property
    def X(self):
        return self.m.X

    def thermal_column(self, dT_member: np.ndarray) -> np.ndarray:
        """任意逐杆件温升分布 → 全自由度位移（支座固定，线性）。"""
        F = self.m.thermal_load(np.asarray(dT_member, float))
        return self.m.solve_many(F[None, :])[0]

    def point_rows(self, nodes, offsets=None) -> np.ndarray:
        """返回 (k,3,ndof) 选取矩阵：点位移 = u_q + θ_q × ρ（小转角，ρ 为相位中心相对节点偏置）。"""
        nodes = np.atleast_1d(nodes).astype(int)
        P = np.zeros((len(nodes), 3, self.m.ndof))
        for k, q in enumerate(nodes):
            for c in range(3):
                P[k, c, 6 * q + c] = 1.0
            if offsets is not None:
                r = np.asarray(offsets[k], float)
                # θ×ρ = [θy rz − θz ry, θz rx − θx rz, θx ry − θy rx]
                P[k, 0, 6 * q + 4] += r[2]; P[k, 0, 6 * q + 5] -= r[1]
                P[k, 1, 6 * q + 5] += r[0]; P[k, 1, 6 * q + 3] -= r[2]
                P[k, 2, 6 * q + 3] += r[1]; P[k, 2, 6 * q + 4] -= r[0]
        return P


def build_model(kind: str = "suspension") -> TowerModel:
    g = build_tower(kind)
    m = fem.FEModel(g).fix_base()
    m.factorize()
    base = list(g.meta["base_nodes"])
    cases = []
    for b in base:
        for c in range(3):
            cases.append((None, {6 * b + c: 1.0}))
    _, Ub = m.influence_matrix(cases, [0])
    Gb = Ub.T
    GT1 = m.solve_many(m.thermal_load(np.ones(g.n_members))[None, :])[0]
    Fw = np.array([loads.wind_static(m, w0=W_UNIT, direction=d) for d in ((1.0, 0, 0), (0, 1.0, 0))])
    Gw = m.solve_many(Fw).T
    return TowerModel(g=g, m=m, base=base, Gb=Gb, GT1=GT1, Gw=Gw, H=float(g.meta["H_total"]))
