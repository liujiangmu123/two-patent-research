# -*- coding: utf-8 -*-
"""对比方法：
  ① 人工靶点：在少数可见节点上设置/识别靶点，各相机测二维像面位移，多相机最小二乘求靶点三维位移，再做 SSI；
  ② 全像素/全部采样带位移 + 盲源分离（SOBI）：不使用桁架图观测算子，只得频率与像面振型；
  ③ 单台相机：观测算子秩亏，面外分量不可观测。
"""
from __future__ import annotations

import numpy as np

from . import oma as OMA


def target_triangulate(cams, nodes_xyz, disp_true, rng, sig_px=0.01, shake_res=None, tau_res=None, dt=0.02):
    """人工靶点多相机三角化。disp_true (nt, k, 3)：k 个靶点的真值三维位移。
    shake_res[c] (nt,3)：第 c 台相机补偿后的残余转角；tau_res[c]：残余时间偏差（s）。
    返回最小二乘三维位移估计 (nt, k, 3)。"""
    from .synth import frac_delay
    nt, k, _ = disp_true.shape
    out = np.zeros_like(disp_true)
    Js = [c.jacobian(nodes_xyz) for c in cams]          # 每相机 (k,2,3)
    uvs = [c.project(nodes_xyz) for c in cams]
    Gs = [c.rotation_flow_jacobian(uv) for c, uv in zip(cams, uvs)]
    obs = []
    for ci in range(len(cams)):
        d = disp_true if not tau_res or not tau_res[ci] else frac_delay(disp_true, tau_res[ci], dt)
        y = np.einsum("tpj,pij->tpi", d, Js[ci]) + rng.normal(0, sig_px, (nt, k, 2))
        if shake_res is not None and shake_res[ci] is not None:
            y = y + np.einsum("pij,tj->tpi", Gs[ci], shake_res[ci])
        obs.append(y)
    for p in range(k):
        A = np.concatenate([J[p] for J in Js], 0)       # (2K,3)
        y = np.concatenate([o[:, p, :] for o in obs], 1)
        out[:, p, :] = y @ np.linalg.pinv(A).T
    return out


def serep_expand(phi_meas, Phi_rows, Phi_full, keep=None, rcond=1e-2):
    """SEREP 振型扩展：以名义振型基中 keep 指定的阶（默认前 8 阶）把测点振型扩展到全部节点自由度；
    截断奇异值（rcond，相对最大奇异值）以避免测点处近零的局部模态放大噪声。"""
    keep = np.arange(min(8, Phi_rows.shape[1])) if keep is None else np.asarray(keep)
    B = Phi_rows[:, keep]
    c = np.linalg.lstsq(B, phi_meas, rcond=rcond)[0]
    return Phi_full[:, keep] @ c


def sobi(X, n_src=10, lags=(1, 2, 3, 5, 8, 12, 17, 25, 35, 50), iters=100):
    """二阶盲辨识（白化 + 多时延协方差联合近似对角化，Jacobi 旋转）。X: (nt, n)。返回源 (nt, n_src) 与混合矩阵。"""
    Xc = X - X.mean(0)
    C = Xc.T @ Xc / len(Xc)
    d, E = np.linalg.eigh(C)
    idx = np.argsort(d)[::-1][:n_src]
    Wh = (E[:, idx] / np.sqrt(d[idx] + 1e-30)).T
    Z = Xc @ Wh.T
    Ms = []
    for tau in lags:
        R = Z[tau:].T @ Z[:-tau] / (len(Z) - tau)
        Ms.append(0.5 * (R + R.T))
    M = np.stack(Ms)
    V = np.eye(n_src)
    for _ in range(iters):
        changed = False
        for p in range(n_src - 1):
            for q in range(p + 1, n_src):
                g = np.stack([M[:, p, p] - M[:, q, q], M[:, p, q] + M[:, q, p]], 1)
                G = g.T @ g
                ton, toff = G[0, 0] - G[1, 1], G[0, 1] + G[1, 0]
                th = 0.5 * np.arctan2(toff, ton + np.sqrt(ton * ton + toff * toff))
                c, s = np.cos(th), np.sin(th)
                if abs(s) > 1e-8:
                    changed = True
                    Mp, Mq = M[:, :, p].copy(), M[:, :, q].copy()
                    M[:, :, p], M[:, :, q] = c * Mp + s * Mq, -s * Mp + c * Mq
                    Mp, Mq = M[:, p, :].copy(), M[:, q, :].copy()
                    M[:, p, :], M[:, q, :] = c * Mp + s * Mq, -s * Mp + c * Mq
                    Vp, Vq = V[:, p].copy(), V[:, q].copy()
                    V[:, p], V[:, q] = c * Vp + s * Vq, -s * Vp + c * Vq
        if not changed:
            break
    S = Z @ V
    return S, np.linalg.pinv(Wh) @ V


def source_modes(S, fs, band=(0.4, 10.0)):
    """每个源取功率谱主峰频率，并以单通道 SSI 估阻尼（失败则半功率带宽法）。"""
    from scipy import signal
    out = []
    for k in range(S.shape[1]):
        f, P = signal.welch(S[:, k], fs=fs, nperseg=4096)
        m = (f > band[0]) & (f < band[1])
        if not m.any():
            continue
        j = np.flatnonzero(m)[np.argmax(P[m])]
        fk = f[j]
        half = P[j] / 2
        lo = j
        while lo > 0 and P[lo] > half:
            lo -= 1
        hi = j
        while hi < len(P) - 1 and P[hi] > half:
            hi += 1
        z = (f[hi] - f[lo]) / (2 * fk) if fk > 0 else np.nan
        out.append({"f": float(fk), "zeta": float(z), "src": k, "power": float(P[j])})
    return sorted(out, key=lambda d: d["f"])
