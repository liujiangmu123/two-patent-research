# -*- coding: utf-8 -*-
"""相机自振补偿（权利要求 7、8）。

相机绕光心的小转动 ω（相机系）引起的像点位移 δu = G(u)·ω 与景深无关；远景背景点（远山、远处建筑等，
深度远大于相机至塔距离）的像面运动只含转动分量，可逐帧最小二乘解出 ω(t)，再按 G(u_s)·ω 扣除各采样点的
诱导位移。可选融合与相机刚性固连的惯性测量单元（陀螺）角速度：背景点估计提供低频（无漂移），陀螺积分提供高频。
"""
from __future__ import annotations

import numpy as np


def horizon_row(cam):
    """相机视向方位上远处地平线（与相机等高）在像面的行坐标。"""
    d = cam.R[2].copy()
    d[2] = 0.0
    d /= np.linalg.norm(d)
    return float(cam.project((cam.C + 1e5 * d)[None])[0, 1])


def background_points(cam, n=24, rng=None, avoid_uv=None, avoid_px=120.0, strip=(-60.0, 140.0), margin=30.0):
    """在远景地平线附近的条带内选取背景特征点（避开塔体投影附近）。条带不在画面内时返回空数组。"""
    rng = rng or np.random.default_rng(0)
    vh = horizon_row(cam)
    v0, v1 = max(margin, vh + strip[0]), min(cam.H - margin, vh + strip[1])
    if v1 - v0 < 8:
        return np.zeros((0, 2))
    pts = []
    tries = 0
    while len(pts) < n and tries < 200 * n:
        tries += 1
        u = rng.uniform(margin, cam.W - margin)
        v = rng.uniform(v0, v1)
        if avoid_uv is not None and len(avoid_uv) and np.min(np.linalg.norm(avoid_uv - [u, v], axis=1)) < avoid_px:
            continue
        pts.append((u, v))
    return np.array(pts).reshape(-1, 2)


def estimate_rotation(G_bg, flow_bg):
    """逐帧最小二乘：flow_bg (nt, nb, 2) = G_bg (nb,2,3) · ω(t)。返回 ω̂ (nt,3)。"""
    A = G_bg.reshape(-1, 3)
    return flow_bg.reshape(flow_bg.shape[0], -1) @ np.linalg.pinv(A).T


def rotation_cov(G_bg, sig_px):
    """背景点估计 ω 的协方差（rad²），用于评估补偿精度。"""
    A = G_bg.reshape(-1, 3)
    return sig_px ** 2 * np.linalg.inv(A.T @ A)


def gyro_series(omega, dt, rng, arw=2.6e-5, bias_instab=2e-6, bias0=1e-5):
    """由真值转角 ω(t) 生成陀螺角速度观测：真值角速度 + 白噪声（角随机游走 arw, rad/√s）+ 慢变零偏。"""
    nt = len(omega)
    rate = np.gradient(omega, dt, axis=0)
    white = rng.standard_normal((nt, 3)) * arw / np.sqrt(dt)
    bias = bias0 * rng.standard_normal(3)[None, :] + np.cumsum(rng.standard_normal((nt, 3)), 0) * bias_instab * np.sqrt(dt)
    return rate + white + bias


def fuse_imu(omega_bg, gyro_rate, dt, fc=0.5):
    """互补滤波：背景点估计取低频，陀螺积分取高频（二阶巴特沃斯，零相位）。"""
    from scipy import signal
    ang = np.cumsum(gyro_rate, axis=0) * dt
    sos = signal.butter(2, fc, btype="low", fs=1.0 / dt, output="sos")
    lo = signal.sosfiltfilt(sos, omega_bg, axis=0)
    hi = ang - signal.sosfiltfilt(sos, ang, axis=0)
    return lo + hi


def induced_normal_disp(G_s, nrm, omega):
    """相机转动在各采样点法向诱导的像面位移 (nt, n_obs)。"""
    gn = np.einsum("sij,si->sj", G_s, nrm)        # (n_obs, 3)
    return omega @ gn.T
