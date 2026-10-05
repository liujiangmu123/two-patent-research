# -*- coding: utf-8 -*-
"""带电安全壳：按电压等级取 DL/T 409（GB 26859/26860 同口径）人身与带电体最小安全距离，
叠加无人机定位误差裕度、阵风漂移裕度与机体半径，形成以导线/绝缘子串为轴的胶囊体并集；
另设对塔体结构与地面的避障距离。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# DL/T 409-1991《电业安全工作规程（电力线路部分）》表 1 / GB 26859-2011 表 1：
# 工作人员工作中正常活动范围与带电设备的安全距离（m，交流）。750/1000 kV 按 GB 26859 补充值。
DLT409_TABLE = {10: 0.7, 35: 1.0, 66: 1.5, 110: 1.5, 220: 3.0, 330: 4.0, 500: 5.0, 750: 8.0, 1000: 9.5}


def min_distance_dlt409(kv: float) -> float:
    """取不低于给定电压的最近一档。"""
    ks = sorted(DLT409_TABLE)
    for k in ks:
        if kv <= k + 1e-9:
            return DLT409_TABLE[k]
    return DLT409_TABLE[ks[-1]]


def seg_dist(P, A, B):
    """点集 P (n,3) 到线段 AB 的距离。"""
    P = np.atleast_2d(P)
    ab = B - A
    t = np.clip(((P - A) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return np.linalg.norm(P - (A + t[:, None] * ab), axis=1)


@dataclass
class SafetyShell:
    live: list                       # [(p0,p1,kind)]
    kv: float = 220.0
    sigma_pos: float = 0.5           # 定位误差（1σ，m；非 RTK 取 0.5，RTK 可取 0.05）
    k_sigma: float = 3.0
    gust_drift: float = 1.0          # 阵风/控制跟踪漂移裕度
    r_uav: float = 0.6               # 机体包络半径
    d_struct: float = 4.0            # 对塔体结构最小距离（避碰）
    z_min: float = 5.0               # 最低飞行高度
    tower_pts: np.ndarray = None     # 塔体结构采样点（避碰用）
    grounded: list = None            # 地线：按结构避碰距离处理

    @property
    def d_min(self):
        return min_distance_dlt409(self.kv)

    @property
    def radius(self):
        """安全壳半径 = 规程最小距离 + kσ 定位误差 + 漂移 + 机体半径。"""
        return self.d_min + self.k_sigma * self.sigma_pos + self.gust_drift + self.r_uav

    def live_distance(self, P):
        P = np.atleast_2d(P)
        d = np.full(len(P), np.inf)
        for a, b, _ in self.live:
            d = np.minimum(d, seg_dist(P, np.asarray(a, float), np.asarray(b, float)))
        return d

    def struct_distance(self, P):
        P = np.atleast_2d(P)
        d = np.full(len(P), np.inf)
        if self.tower_pts is not None:
            from scipy.spatial import cKDTree
            if not hasattr(self, "_kd"):
                self._kd = cKDTree(self.tower_pts)
            d = self._kd.query(P)[0]
        for a, b, _ in (self.grounded or []):
            d = np.minimum(d, seg_dist(P, np.asarray(a, float), np.asarray(b, float)))
        return d

    def is_safe(self, P, struct=True):
        P = np.atleast_2d(P)
        ok = (self.live_distance(P) >= self.radius) & (P[:, 2] >= self.z_min)
        if struct:
            ok &= self.struct_distance(P) >= self.d_struct
        return ok

    def segment_safe(self, a, b, step=0.5):
        a, b = np.asarray(a, float), np.asarray(b, float)
        n = max(2, int(np.linalg.norm(b - a) / step) + 1)
        P = a + np.linspace(0, 1, n)[:, None] * (b - a)
        return bool(self.is_safe(P).all())

    def violations(self, path_pts, step=0.5):
        """沿航迹（按 step 重采样）统计侵入带电安全壳的连续区段数与采样点数。"""
        P = resample(np.asarray(path_pts, float), step)
        bad = self.live_distance(P) < self.radius
        n_seg = int(np.sum(bad[1:] & ~bad[:-1]) + (1 if bad.size and bad[0] else 0))
        return {"segments": n_seg, "samples": int(bad.sum()), "min_live_dist": float(self.live_distance(P).min()),
                "radius": self.radius}


def tower_samples(g, step=0.5):
    X = g.nodes
    pts = []
    for a, b in zip(g.mi, g.mj):
        n = max(2, int(np.linalg.norm(X[b] - X[a]) / step) + 1)
        pts.append(X[a] + np.linspace(0, 1, n)[:, None] * (X[b] - X[a]))
    return np.concatenate(pts)


def resample(P, step):
    if len(P) < 2:
        return P
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] <= 0:
        return P[:1]
    q = np.linspace(0, s[-1], max(2, int(s[-1] / step) + 1))
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], axis=1)
