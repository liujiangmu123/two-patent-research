# -*- coding: utf-8 -*-
"""安全壳外候选视点：围绕塔体的多半径、多高度、多方位栅格，滤除带电安全壳、结构避碰区与地面以下点；
每个视点机头朝向塔轴、云台俯仰指向同高度塔轴（限幅），预测驻留期内对每根杆件的期望点数与视角扇区。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ._tk import lidar as L
from .confidence import N_BINS, view_bins


@dataclass
class Candidates:
    pos: np.ndarray        # (V,3)
    yaw: np.ndarray        # (V,)
    pitch: np.ndarray      # (V,) 云台俯仰（°，向上为正）
    hits: np.ndarray       # (V, M) 期望点数（全点频，驻留 dwell）
    vbin: np.ndarray       # (V, M) 视角扇区
    dwell: float


def generate(sc, shell, radii=(9.0, 13.0, 18.0, 24.0), dz=4.0, n_az=24, z_lo=3.0, z_extra=6.0):
    H = sc.meta["H"]
    pts = []
    for r in radii:
        for z in np.arange(z_lo, H + z_extra + 1e-6, dz):
            for k in range(n_az):
                a = 2 * np.pi * (k + 0.5 * (int(z / dz) % 2)) / n_az
                pts.append([r * math.cos(a), r * math.sin(a), z])
    # 塔顶上方
    for x in (-6.0, 0.0, 6.0):
        for y in (-8.0, 8.0):
            pts.append([x, y, H + z_extra])
    P = np.asarray(pts)
    ok = shell.is_safe(P)
    return P[ok], P[~ok]


def aim(P, target_z=None, pitch_lim=(-60.0, 45.0)):
    yaw = np.arctan2(-P[:, 1], -P[:, 0])
    rh = np.linalg.norm(P[:, :2], axis=1)
    tz = P[:, 2] if target_z is None else target_z
    pitch = np.degrees(np.arctan2(tz - P[:, 2], np.maximum(rh, 1e-3)))
    return yaw, np.clip(pitch, *pitch_lim)


def predict(geom, prior, P, yaw, pitch, scanner, dwell=4.0, n_sample=12000, seed=0):
    """用规划几何（设计先验，不含未知遮挡物）预测期望点数。"""
    V = len(P)
    hits = np.zeros((V, geom.n_members))
    for v in range(V):
        R = L.Mount(yaw=0.0, pitch=float(pitch[v]), lever=(0, 0, 0)).R()
        hits[v] = L.expected_hits(geom, P[v:v + 1], scanner, [R], dwell=dwell, n_sample=n_sample, seed=seed + v,
                                  yaw=yaw[v:v + 1])[0]
    X = prior.nodes; mi, mj = np.asarray(prior.mi), np.asarray(prior.mj)
    vb = np.zeros((V, prior.n_members), int)
    for v in range(V):
        vb[v] = view_bins(X, mi, mj, np.arange(prior.n_members), np.repeat(P[v:v + 1], prior.n_members, 0))
    return Candidates(P, yaw, pitch, hits, vb, dwell)


def hover_scan(geom, p, yaw, pitch, scanner, dwell, seed, decim):
    tr = L.Trajectory(np.array([0.0, dwell]), np.stack([p, p]), np.array([yaw, yaw]))
    m = L.Mount(yaw=0.0, pitch=float(pitch), lever=(0, 0, 0))
    return L.scan(geom, tr, scanner, m, seed=seed, decim=decim, pos_sigma=0.03)


__all__ = ["Candidates", "generate", "aim", "predict", "hover_scan", "N_BINS"]
