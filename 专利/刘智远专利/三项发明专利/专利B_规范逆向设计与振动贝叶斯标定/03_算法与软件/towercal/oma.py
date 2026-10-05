# -*- coding: utf-8 -*-
"""协方差驱动随机子空间识别（SSI-COV）+ 稳定图自动拾取。

步骤：去均值/去趋势与带通 → 输出协方差 R_k → 块 Toeplitz 矩阵 → SVD → 各阶次 (A, C) →
极点 → 稳定性判据（频率、阻尼、MAC）→ 层次聚类 → 每簇中位数作为识别模态。
"""
from __future__ import annotations

import numpy as np
from scipy import signal


def preprocess(y, fs, band=(0.5, 8.0), decim=1):
    y = signal.detrend(y, axis=0, type="linear")
    sos = signal.butter(4, [band[0], band[1]], btype="band", fs=fs, output="sos")
    y = signal.sosfiltfilt(sos, y, axis=0)
    if decim > 1:
        y = y[::decim]
        fs = fs / decim
    return y, fs


def ssi_cov(y, fs, i=30, orders=range(10, 61, 2), ref=None):
    """返回所有阶次极点列表 [(order, f, zeta, phi)]。y: (nt, nch)。ref: 参考通道索引。"""
    nt, l = y.shape
    ref = np.arange(l) if ref is None else np.asarray(ref)
    r = len(ref)
    yr = y[:, ref]
    N = nt - 2 * i
    R = [y[k:k + N].T @ yr[:N] / N for k in range(1, 2 * i + 1)]    # R_k, k=1..2i, (l, r)
    T = np.zeros((l * i, r * i))
    for a in range(i):
        for b in range(i):
            T[a * l:(a + 1) * l, b * r:(b + 1) * r] = R[i + a - b - 1]
    U, s, Vt = np.linalg.svd(T, full_matrices=False)
    poles = []
    for n in orders:
        n = min(n, len(s))
        O = U[:, :n] * np.sqrt(s[:n])
        C = O[:l]
        A = np.linalg.lstsq(O[:-l], O[l:], rcond=None)[0]
        lam, psi = np.linalg.eig(A)
        mu = np.log(lam.astype(complex)) * fs
        f = np.abs(mu) / 2 / np.pi
        z = -mu.real / np.abs(mu)
        phi = C @ psi
        for k in range(len(lam)):
            if lam[k].imag > 0 and 0 < z[k] < 0.2:
                poles.append((n, float(f[k]), float(z[k]), phi[:, k]))
    return poles, s


def _mac(a, b):
    return float(np.abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real + 1e-300))


def stable_poles(poles, df=0.01, dz=0.05, dmac=0.02):
    by = {}
    for p in poles:
        by.setdefault(p[0], []).append(p)
    ords = sorted(by)
    st = []
    for a, b in zip(ords[:-1], ords[1:]):
        for p in by[b]:
            for q in by[a]:
                if abs(p[1] - q[1]) / q[1] < df and abs(p[2] - q[2]) / max(q[2], 1e-6) < dz * 10 \
                        and 1 - _mac(p[3], q[3]) < dmac:
                    st.append(p)
                    break
    return st


def cluster_modes(st, fmin=0.5, fmax=8.0, ftol=0.015, min_count=5, mac_tol=0.8):
    st = sorted([p for p in st if fmin < p[1] < fmax], key=lambda p: p[1])
    clusters = []
    for p in st:
        for c in clusters:
            fc = np.median([q[1] for q in c])
            if abs(p[1] - fc) / fc < ftol and _mac(p[3], c[0][3]) > mac_tol:
                c.append(p)
                break
        else:
            clusters.append([p])
    modes = []
    for c in clusters:
        if len(c) < min_count:
            continue
        f = np.array([q[1] for q in c]); z = np.array([q[2] for q in c])
        k = int(np.argmin(np.abs(f - np.median(f))))
        ph = c[k][3]
        ph = ph * np.exp(-1j * np.angle(ph[np.argmax(np.abs(ph))]))
        modes.append({"f": float(np.median(f)), "zeta": float(np.median(z)), "f_std": float(f.std()),
                      "phi": ph.real / np.linalg.norm(ph.real), "count": len(c),
                      "mpc_imag": float(np.linalg.norm(ph.imag) / np.linalg.norm(ph))})
    return modes


def identify(y, fs, band=(0.5, 8.0), decim=1, i=30, orders=range(10, 61, 2), min_count=5):
    y, fs2 = preprocess(y, fs, band, decim)
    poles, s = ssi_cov(y, fs2, i, orders)
    st = stable_poles(poles)
    return cluster_modes(st, band[0], band[1], min_count=min_count), {"poles": len(poles), "stable": len(st)}
