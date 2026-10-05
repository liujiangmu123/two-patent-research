# -*- coding: utf-8 -*-
"""桁架图投影、可见性筛选、法向边缘采样带生成与采样带内亚像素法向位移估计。

采样带：以投影杆件上的采样点为中心、沿杆件切向长 band_len 像素、沿像面法向宽（杆件投影宽度 + 两侧余量）的矩形窗口；
带内每行是一条跨越杆件两侧边缘的法向灰度剖面，法向位移由全部行联合估计（权利要求 3、4）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import _tk  # noqa: F401
from towerkit import lidar as L
from towerkit import sections as S


@dataclass
class Samples:
    member: np.ndarray     # (n,)
    t: np.ndarray          # (n,) 插值系数
    node_i: np.ndarray
    node_j: np.ndarray
    uv: np.ndarray         # (n,2)
    nrm: np.ndarray        # (n,2) 像面单位法向
    J: np.ndarray          # (n,2,3) 投影雅可比
    width_px: np.ndarray   # (n,) 投影宽度
    depth: np.ndarray      # (n,)

    @property
    def n(self):
        return len(self.member)


def project_depth(cam, P):
    """世界点 → (像素 (n,2), 景深 (n,))。"""
    P = np.atleast_2d(np.asarray(P, float))
    z = ((P - cam.C) @ cam.R.T)[:, 2]
    return cam.project(P), z


def visible_members(g, geom: L.Geometry, cam, n_check=5, min_len_px=40.0, min_angle_deg=20.0, tol=0.08,
                    min_vis=0.8):
    """返回可见杆件列表：投影长度、与视线夹角达标，且杆件中段检查点未被其他杆件遮挡（权利要求 2）。"""
    X = g.nodes
    mi, mj = g.ends()
    out = []
    ts = np.linspace(0.2, 0.8, n_check)
    for e in range(g.n_members):
        a, b = X[mi[e]], X[mj[e]]
        uv, z = project_depth(cam, np.stack([a, b]))
        if np.any(z < 1.0):
            continue
        if np.linalg.norm(uv[1] - uv[0]) < min_len_px:
            continue
        if np.any((uv[:, 0] < 0) | (uv[:, 1] < 0) | (uv[:, 0] >= cam.W) | (uv[:, 1] >= cam.H)):
            continue
        mid = 0.5 * (a + b)
        ray = mid - cam.C; ray /= np.linalg.norm(ray)
        ax = (b - a) / np.linalg.norm(b - a)
        ang = np.degrees(np.arccos(np.clip(abs(ray @ ax), 0, 1)))
        if ang < min_angle_deg:
            continue
        P = a + ts[:, None] * (b - a)
        d = P - cam.C
        dist = np.linalg.norm(d, axis=1)
        d /= dist[:, None]
        th, kh = L.cast_rays(geom, np.repeat(cam.C[None], len(P), 0), d, float(dist.max() + 1))
        vis = (kh < 0) | (th >= dist - tol) | (geom.member[np.maximum(kh, 0)] == e)
        if vis.mean() >= min_vis:
            out.append(e)
    return np.array(out, int)


def band_samples(g, cam, members, spacing_px=30.0, t_range=(0.15, 0.85)) -> Samples:
    X = g.nodes
    mi, mj = g.ends()
    rec = {k: [] for k in ("m", "t", "i", "j", "uv", "n", "J", "w", "z")}
    for e in members:
        a, b = X[mi[e]], X[mj[e]]
        uv, z = project_depth(cam, np.stack([a, b]))
        L_px = np.linalg.norm(uv[1] - uv[0])
        ns = max(1, int(L_px * (t_range[1] - t_range[0]) / spacing_px))
        ts = np.linspace(t_range[0], t_range[1], ns + 2)[1:-1] if ns > 1 else np.array([0.5])
        P = a + ts[:, None] * (b - a)
        q, zz = project_depth(cam, P)
        tan = (uv[1] - uv[0]) / L_px
        nrm = np.array([-tan[1], tan[0]])
        Jm = cam.jacobian(P)
        bw = S.angle(g.sec[e]).b if g.sec[e] else 0.07
        for k in range(len(ts)):
            rec["m"].append(e); rec["t"].append(ts[k]); rec["i"].append(mi[e]); rec["j"].append(mj[e])
            rec["uv"].append(q[k]); rec["n"].append(nrm); rec["J"].append(Jm[k]); rec["w"].append(1.1 * bw * cam.f / zz[k])
            rec["z"].append(zz[k])
    A = lambda k, dt=float: np.asarray(rec[k], dt)
    return Samples(A("m", int), A("t"), A("i", int), A("j", int), A("uv").reshape(-1, 2), A("n").reshape(-1, 2),
                   A("J").reshape(-1, 2, 3), A("w"), A("z"))


# ====================================================================== 采样带内亚像素法向位移
def band_shift_gradient(ref, cur, iters=3):
    """梯度法（一维 Lucas–Kanade，带内全部行联合）：返回 cur 相对 ref 的法向平移（px）。ref/cur: (rows, cols)。"""
    x = np.arange(ref.shape[1], dtype=float)
    d = 0.0
    for _ in range(iters):
        warped = np.stack([np.interp(x + d, x, row) for row in cur])
        g = np.gradient(0.5 * (ref + warped), axis=1)
        num = np.sum(g * (warped - ref))
        den = np.sum(g * g) + 1e-12
        d -= num / den
    return float(d)


def phase_kernel(n, width_px):
    """沿法向的复值方向滤波器（Gabor，零直流修正）。波长取杆件投影宽度的 2 倍加 4 像素。返回 (ker, k)。"""
    lam = max(2.0 * width_px + 4.0, 6.0)
    k = 2 * np.pi / lam
    x = np.arange(n, dtype=float)
    xc = x.mean()
    env = np.exp(-0.5 * ((x - xc) / (0.5 * lam)) ** 2)
    ker = env * np.exp(1j * k * (x - xc))
    ker = ker - env * (ker.sum() / env.sum())          # Σker = 0，消除背景亮度对相位的影响
    return ker, k


def band_shift_phase(ref, cur, width_px, iters=2):
    """复值方向滤波器局部相位法（权利要求 3）：带内各行与滤波器卷积得局部相位，相邻帧与参考帧的相位差以
    局部相位幅值加权平均后除以滤波器空间频率得法向位移；按估计值重采样后再迭代一次以消除包络截断偏差。"""
    ker, k = phase_kernel(ref.shape[1], width_px)
    x = np.arange(ref.shape[1], dtype=float)
    a = (ref - ref.mean(1, keepdims=True)) @ ker
    d = 0.0
    for _ in range(iters):
        cw = np.stack([np.interp(x + d, x, row) for row in cur]) if d else cur
        b = (cw - cw.mean(1, keepdims=True)) @ ker
        w = np.abs(a) * np.abs(b)
        d += float(np.angle(np.sum(w * np.exp(1j * (np.angle(b) - np.angle(a)))))) / k
    return float(d)
