# -*- coding: utf-8 -*-
"""运行模态识别：协方差驱动随机子空间法（SSI-COV，稳定图 + 聚类）与频域分解（FDD），模态置信准则 MAC。"""
from __future__ import annotations

import numpy as np
from scipy import signal


def mac(a, b):
    a = np.asarray(a); b = np.asarray(b)
    return float(np.abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real + 1e-300))


def mac_matrix(A, B):
    return np.array([[mac(A[:, i], B[:, j]) for j in range(B.shape[1])] for i in range(A.shape[1])])


def preprocess(y, fs, band=(0.4, 10.0)):
    y = signal.detrend(y, axis=0)
    sos = signal.butter(4, list(band), btype="band", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, y, axis=0)


def ssi_cov(y, fs, i=40, orders=range(8, 61, 2)):
    nt, l = y.shape
    N = nt - 2 * i
    R = [y[k:k + N].T @ y[:N] / N for k in range(1, 2 * i + 1)]
    T = np.zeros((l * i, l * i))
    for a in range(i):
        for b in range(i):
            T[a * l:(a + 1) * l, b * l:(b + 1) * l] = R[i + a - b - 1]
    U, s, Vt = np.linalg.svd(T, full_matrices=False)
    poles = []
    for n in orders:
        n = min(n, len(s))
        O = U[:, :n] * np.sqrt(s[:n])
        C = O[:l]
        A = np.linalg.lstsq(O[:-l], O[l:], rcond=None)[0]
        lam, psi = np.linalg.eig(A)
        mu = np.log(lam.astype(complex)) * fs
        f = np.abs(mu) / (2 * np.pi)
        z = -mu.real / np.abs(mu)
        phi = C @ psi
        for k in range(len(lam)):
            if lam[k].imag > 0 and 0 < z[k] < 0.15:
                poles.append((n, float(f[k]), float(z[k]), phi[:, k]))
    return poles


def stable_modes(poles, fmin=0.4, fmax=10.0, df=0.01, dz=0.3, dmac=0.03, ftol=0.015, min_count=6):
    by = {}
    for p in poles:
        by.setdefault(p[0], []).append(p)
    ords = sorted(by)
    st = []
    for a, b in zip(ords[:-1], ords[1:]):
        for p in by[b]:
            for q in by[a]:
                if abs(p[1] - q[1]) / q[1] < df and abs(p[2] - q[2]) / max(q[2], 1e-6) < dz and 1 - mac(p[3], q[3]) < dmac:
                    st.append(p)
                    break
    st = sorted([p for p in st if fmin < p[1] < fmax], key=lambda p: p[1])
    clusters = []
    for p in st:
        for c in clusters:
            fc = np.median([q[1] for q in c])
            if abs(p[1] - fc) / fc < ftol and mac(p[3], c[0][3]) > 0.8:
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
        modes.append({"f": float(np.median(f)), "zeta": float(np.median(z)), "phi": ph.real, "count": len(c),
                      "mpc": float(1 - np.linalg.norm(ph.imag) / (np.linalg.norm(ph) + 1e-30))})
    return modes


def identify(y, fs, band=(0.4, 10.0), i=40, orders=range(8, 61, 2), min_count=6):
    yp = preprocess(y, fs, band)
    return stable_modes(ssi_cov(yp, fs, i, orders), band[0], band[1], min_count=min_count)


def fdd_peaks(y, fs, n_peaks=8, band=(0.4, 10.0), nperseg=4096):
    """频域分解：互谱矩阵逐频 SVD，第一奇异值峰值对应频率与奇异向量（振型）。"""
    f, _ = signal.welch(y[:, 0], fs=fs, nperseg=nperseg)
    l = y.shape[1]
    G = np.zeros((len(f), l, l), complex)
    for a in range(l):
        for b in range(a, l):
            _, p = signal.csd(y[:, a], y[:, b], fs=fs, nperseg=nperseg)
            G[:, a, b] = p
            G[:, b, a] = np.conj(p)
    s1 = np.zeros(len(f)); u1 = np.zeros((len(f), l), complex)
    for k in range(len(f)):
        U, s, _ = np.linalg.svd(G[k])
        s1[k], u1[k] = s[0], U[:, 0]
    m = (f > band[0]) & (f < band[1])
    idx = signal.find_peaks(np.log(s1 + 1e-30) * m, prominence=1.0)[0]
    idx = idx[np.argsort(-s1[idx])][:n_peaks]
    idx = np.sort(idx)
    return [{"f": float(f[k]), "phi": np.real(u1[k] * np.exp(-1j * np.angle(u1[k][np.argmax(np.abs(u1[k]))])))} for k in idx]


def match_modes(est, f_true, shapes_true, est_shapes, f_tol=0.05, mac_min=0.6):
    """把识别模态与真值模态一一匹配（按 MAC 最大且频率相差 < f_tol）。返回 [(true_k, est_k, f_err, mac)]。"""
    used = set()
    out = []
    for k in range(len(f_true)):
        best = None
        for j, e in enumerate(est):
            if j in used:
                continue
            fe = abs(e["f"] - f_true[k]) / f_true[k]
            if fe > f_tol:
                continue
            mv = mac(est_shapes[:, j], shapes_true[:, k])
            if mv >= mac_min and (best is None or mv > best[3]):
                best = (k, j, fe, mv)
        if best:
            used.add(best[1])
            out.append(best)
    return out
