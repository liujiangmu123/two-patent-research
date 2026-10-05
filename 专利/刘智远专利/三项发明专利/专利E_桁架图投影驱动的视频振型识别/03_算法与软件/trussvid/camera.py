# -*- coding: utf-8 -*-
"""针孔相机模型、投影雅可比、地面环形布站与相机自振动（晃动）模型。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def rotvec(w):
    """小转角向量 → 旋转矩阵（Rodrigues）。"""
    w = np.asarray(w, float)
    th = np.linalg.norm(w)
    if th < 1e-15:
        return np.eye(3)
    k = w / th
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx


@dataclass
class Camera:
    """世界→相机：Xc = R (X − C)；像素 u = f·Xc0/Xc2 + cx, v = f·Xc1/Xc2 + cy（x 右、y 下、z 前）。"""
    C: np.ndarray
    R: np.ndarray
    f: float
    W: int
    H: int
    name: str = "cam"
    cx: float = field(default=None)
    cy: float = field(default=None)

    def __post_init__(self):
        self.C = np.asarray(self.C, float)
        self.R = np.asarray(self.R, float)
        if self.cx is None:
            self.cx = (self.W - 1) / 2
        if self.cy is None:
            self.cy = (self.H - 1) / 2

    @classmethod
    def look_at(cls, C, target, f, W, H, name="cam"):
        C = np.asarray(C, float)
        z = np.asarray(target, float) - C
        z /= np.linalg.norm(z)
        x = np.cross(z, [0, 0, 1.0])
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        return cls(C, np.vstack([x, y, z]), f, W, H, name)

    def project(self, X, R=None, C=None):
        """X (...,3) → 像素 (...,2)。R、C 可传入晃动后的姿态。"""
        R = self.R if R is None else R
        C = self.C if C is None else C
        Xc = (np.asarray(X, float) - C) @ R.T
        return np.stack([self.f * Xc[..., 0] / Xc[..., 2] + self.cx,
                         self.f * Xc[..., 1] / Xc[..., 2] + self.cy], -1)

    def jacobian(self, X):
        """像点对世界点位移的雅可比 ∂u/∂X，(...,2,3)。"""
        Xc = (np.asarray(X, float) - self.C) @ self.R.T
        x, y, z = Xc[..., 0], Xc[..., 1], Xc[..., 2]
        J = np.zeros(Xc.shape[:-1] + (2, 3))
        J[..., 0, 0] = self.f / z
        J[..., 0, 2] = -self.f * x / z ** 2
        J[..., 1, 1] = self.f / z
        J[..., 1, 2] = -self.f * y / z ** 2
        return J @ self.R

    def ray(self, uv):
        """像素 → 世界系单位方向。"""
        uv = np.asarray(uv, float)
        d = np.stack([(uv[..., 0] - self.cx) / self.f, (uv[..., 1] - self.cy) / self.f, np.ones(uv.shape[:-1])], -1)
        d = d @ self.R
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def rotation_flow_jacobian(self, uv, eps=1e-5):
        """相机小转动 ω（相机系，R_t = rot(ω)·R）引起的像点位移对 ω 的雅可比 (...,2,3)；与景深无关。"""
        uv = np.asarray(uv, float)
        X = self.C + 1e6 * self.ray(uv)
        G = np.zeros(uv.shape[:-1] + (2, 3))
        for k in range(3):
            w = np.zeros(3); w[k] = eps
            G[..., k] = (self.project(X, R=rotvec(w) @ self.R) - self.project(X, R=rotvec(-w) @ self.R)) / (2 * eps)
        return G


def ring_cameras(n=3, distance=80.0, height=1.5, target=(0, 0, 30.0), azimuths=None, f=None, W=320, H=480,
                 fit_height=61.0, fit_distance=None, margin=0.92):
    """在塔周地面按方位角布站。f 未给定时按 fit_distance（默认=distance）处使塔全高恰好充满画面高度的 margin 比例。"""
    if azimuths is None:
        azimuths = np.deg2rad([20.0, 140.0, 250.0])[:n] if n <= 3 else np.linspace(0, 2 * np.pi, n, endpoint=False)
    cams = []
    for k, az in enumerate(np.asarray(azimuths)[:n]):
        C = [distance * np.cos(az), distance * np.sin(az), height]
        if f is None:
            D = fit_distance or distance
            Cf = [D * np.cos(az), D * np.sin(az), height]
            c0 = Camera.look_at(Cf, target, 1.0, W, H)
            vv = c0.project(np.array([[0, 0, 0.0], [0, 0, fit_height]]))[:, 1]
            f = margin * H / abs(vv[0] - vv[1])
        cams.append(Camera.look_at(C, target, f, W, H, name=f"C{k + 1}"))
    return cams


def shake_series(t, rot_rms=0.0, tr_rms=0.0, band=(0.3, 12.0), seed=0):
    """相机自振动：三轴转角 ω(t)（rad）与平移 δ(t)（m），带限高斯过程，返回 (nt,3),(nt,3)。"""
    rng = np.random.default_rng(seed)
    nt = len(t)
    dt = t[1] - t[0]
    f = np.fft.rfftfreq(nt, dt)
    H = ((f >= band[0]) & (f <= band[1])).astype(float) / np.sqrt(1 + (f / 4.0) ** 2)

    def gen(rms):
        if rms <= 0:
            return np.zeros((nt, 3))
        x = np.fft.irfft(np.fft.rfft(rng.standard_normal((3, nt)), axis=1) * H, n=nt, axis=1).T
        return x / x.std(0) * rms
    return gen(rot_rms), gen(tr_rms)
