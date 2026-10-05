# -*- coding: utf-8 -*-
"""像面观测算子 y = HΦq（权利要求 5）、加权正则化最小二乘逐帧反投影（权利要求 6）、条件数与推荐布站（权利要求 12）、
多相机残余时间偏差估计与频域相位校正（权利要求 9）。"""
from __future__ import annotations

import numpy as np


def obs_rows(samples, n_nodes):
    """H：每个采样点一行，y_s = n_sᵀ J_s [(1−t_s)u_i + t_s u_j]，u 为节点平动（3n）。"""
    ns = samples.n
    H = np.zeros((ns, 3 * n_nodes))
    g = np.einsum("si,sij->sj", samples.nrm, samples.J)          # (ns,3) = n_sᵀ J_s
    for s in range(ns):
        i, j, t = samples.node_i[s], samples.node_j[s], samples.t[s]
        H[s, 3 * i:3 * i + 3] += (1 - t) * g[s]
        H[s, 3 * j:3 * j + 3] += t * g[s]
    return H


def translational(phi, n_nodes):
    """从 6 自由度振型中取节点平动分量 (3n, m)。"""
    P = phi.reshape(n_nodes, 6, -1)[:, :3, :]
    return P.reshape(3 * n_nodes, -1)


def reconstruct(Y, A, w=None, lam=1e-3):
    """q(t) = (AᵀWA + λI)⁻¹AᵀW y(t)，Y: (nt, n_obs)，A: (n_obs, m)。λ 相对 tr(AᵀWA)/m 归一化。"""
    w = np.ones(A.shape[0]) if w is None else np.asarray(w)
    AtW = A.T * w[None, :]
    N = AtW @ A
    lam_abs = lam * np.trace(N) / N.shape[0]
    P = np.linalg.solve(N + lam_abs * np.eye(N.shape[0]), AtW)
    return Y @ P.T, P


def joint_operator(As, Gns, Gbgs, ws, wbgs, lam=1e-4, lam_w=1e-6):
    """模态坐标与各相机自身转动的联合观测算子（权利要求 7 的联合补偿方式）。
    未知量 x = [q (m); ω_1 (3); …; ω_C (3)]；第 c 台相机采样带行 [A_c, …, g_c, …]，g_c = n_sᵀ G(u_s)
    为相机转动在采样点法向诱导的位移；远景背景点行 [0, …, G_bg,c, …]。塔基固定边界附近的采样带只感受相机转动，
    与背景点一同把 ω_c 与结构模态区分开。返回 (A_aug, w_aug, P_aug, n_band_rows)。"""
    C = len(As)
    m = As[0].shape[1]
    nx = m + 3 * C
    blocks, wl = [], []
    for c in range(C):
        B = np.zeros((As[c].shape[0], nx))
        B[:, :m] = As[c]
        B[:, m + 3 * c:m + 3 * c + 3] = Gns[c]
        blocks.append(B); wl.append(np.asarray(ws[c], float))
    nb_rows = sum(b.shape[0] for b in blocks)
    for c in range(C):
        if Gbgs[c] is None or len(Gbgs[c]) == 0:
            continue
        B = np.zeros((Gbgs[c].shape[0], nx))
        B[:, m + 3 * c:m + 3 * c + 3] = Gbgs[c]
        blocks.append(B); wl.append(np.full(Gbgs[c].shape[0], float(wbgs[c])))
    A = np.vstack(blocks); w = np.concatenate(wl)
    AtW = A.T * w[None, :]
    N = AtW @ A
    reg = np.zeros(nx)
    reg[:m] = lam * np.trace(N[:m, :m]) / m
    reg[m:] = lam_w * np.trace(N[m:, m:]) / max(3 * C, 1)
    P = np.linalg.solve(N + np.diag(reg), AtW)
    return A, w, P, nb_rows


def coord_noise_cov(P, w):
    """反投影模态坐标的噪声协方差 Σ_q = P·diag(1/w)·Pᵀ（w 为各采样带权重 = 1/噪声方差）。"""
    return (P / np.asarray(w)[None, :]) @ P.T


def whiten(Q, Sigma):
    """以噪声协方差 Σ_q = L·Lᵀ 白化模态坐标：Q_w = Q·L⁻ᵀ（各通道噪声单位化且互不相关）。返回 (Q_w, L)。"""
    S = 0.5 * (Sigma + Sigma.T)
    S = S + 1e-12 * np.trace(S) / len(S) * np.eye(len(S))
    L = np.linalg.cholesky(S)
    return np.linalg.solve(L, Q.T).T, L


def cond_number(A, w=None):
    w = np.ones(A.shape[0]) if w is None else np.asarray(w)
    s = np.linalg.svd(A * np.sqrt(w)[:, None], compute_uv=False)
    return float(s[0] / max(s[-1], 1e-30))


def recommend_azimuth(A_list, w_list, cand_A, cand_w, cand_az):
    """在候选方位新增一台相机，返回使观测算子条件数最小的方位及各候选条件数。"""
    A0 = np.vstack(A_list); w0 = np.concatenate(w_list)
    out = []
    for Ac, wc in zip(cand_A, cand_w):
        out.append(cond_number(np.vstack([A0, Ac]), np.concatenate([w0, wc])))
    k = int(np.argmin(out))
    return float(cand_az[k]), out


def project(Y, P, chunk=8192):
    """Q = Y·Pᵀ，按时间分块（Y 可为 float32 大数组）。"""
    P32 = P.astype(np.float32)
    out = np.empty((Y.shape[0], P.shape[0]))
    for s in range(0, Y.shape[0], chunk):
        out[s:s + chunk] = Y[s:s + chunk] @ P32.T
    return out


def residual_weights(Y, A, Q, fs=None, band=(0.3, 15.0), floor=1e-4, chunk=256):
    """以反投影残差方差估计各采样带噪声方差（含测量噪声、湍流抖动与模型误差），返回权重 1/σ²。
    fs 给定时先对 Y 与 Q 同一带通滤波（线性运算可交换），按采样带分块计算以控制内存。"""
    Qb = bandpass(Q, fs, band) if fs else Q
    var = np.empty(A.shape[0])
    for s in range(0, A.shape[0], chunk):
        e = min(A.shape[0], s + chunk)
        Yb = bandpass(np.asarray(Y[:, s:e], float), fs, band) if fs else np.asarray(Y[:, s:e], float)
        var[s:e] = (Yb - Qb @ A[s:e].T).var(0)
    dof = max(1e-3, 1.0 - A.shape[1] / max(A.shape[0], 1))
    return 1.0 / np.maximum(var / dof, floor ** 2)


# ====================================================================== 时间偏差
def bandpass(Y, fs, band=(0.4, 8.0)):
    from scipy import signal
    sos = signal.butter(4, list(band), btype="band", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, Y, axis=0)


def estimate_offsets(Ys, As, ws, dt, lam=1e-4, iters=6, ref=0, band=(0.4, 8.0), max_abs=0.05, n_sub=400, seed=0):
    """观测算子一致性时间偏差估计（权利要求 9 的残余偏差估计）：
    y_c(t) = A_c q(t−τ_c) ≈ A_c q(t) − τ_c A_c q̇(t)。交替进行：多相机联合反投影 q̂ → 对每台相机以
    r_c = y_c − A_c q̂ 对 −A_c q̂̇ 作加权最小二乘得 Δτ_c → 频域相位校正 y_c(t+τ_c)。参考相机 τ=0。
    为控制计算量，每台相机均匀抽取 n_sub 个采样带参与估计。返回 τ (n_cam,)。"""
    fs = 1.0 / dt
    rng = np.random.default_rng(seed)
    sel = [np.sort(rng.choice(A.shape[0], min(n_sub, A.shape[0]), replace=False)) for A in As]
    Yb = [bandpass(np.asarray(Y[:, s], float), fs, band) for Y, s in zip(Ys, sel)]
    Ab = [A[s] for A, s in zip(As, sel)]
    wb = [w[s] for w, s in zip(ws, sel)]
    taus = np.zeros(len(Ys))
    cur = [y.copy() for y in Yb]
    A = np.vstack(Ab); w = np.concatenate(wb)
    for _ in range(iters):
        Q, _ = reconstruct(np.hstack(cur), A, w, lam)
        Qd = np.gradient(Q, dt, axis=0)
        for c in range(len(Ys)):
            if c == ref:
                continue
            gp = Qd @ Ab[c].T
            r = cur[c] - Q @ Ab[c].T
            num = np.sum(wb[c][None, :] * r * gp)
            den = np.sum(wb[c][None, :] * gp * gp) + 1e-30
            taus[c] = float(np.clip(taus[c] - num / den, -max_abs, max_abs))
            cur[c] = frac_delay(Yb[c], -taus[c], dt)
    return taus


def frac_delay_inplace(Y, tau, dt, chunk=256):
    """对 float32 大数组按采样带分块做频域分数延迟 Y(t) ← Y(t−tau)。"""
    for s in range(0, Y.shape[1], chunk):
        Y[:, s:s + chunk] = frac_delay(np.asarray(Y[:, s:s + chunk], float), tau, dt)
    return Y


def frac_delay(x, tau, dt):
    nt = x.shape[0]
    f = np.fft.rfftfreq(nt, dt)
    X = np.fft.rfft(x, axis=0)
    ph = np.exp(-2j * np.pi * f * tau)
    return np.fft.irfft(X * ph.reshape((-1,) + (1,) * (x.ndim - 1)), n=nt, axis=0)
