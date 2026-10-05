# -*- coding: utf-8 -*-
"""S5/S6/S7：视线向观测算子组装、升降轨联合时序正则化最小二乘反演、倾斜与预警。

观测：每几何 g 的 PS k 在景 t 的视线向位移（相对该几何参考景 t_ref,g 与塔外稳定参考点）
    d_k(t) = h_k(t)·x(t) − h_k(t_ref,g)·x(t_ref,g) + ε
x(t) = [b(t)(12)；τ1(t), τ2(t)；w_x(t), w_y(t)]，h_k(t)=lᵀ P_k [G_b, G_T1, G_T2(t), G_w]。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

NB, NP = 12, 4            # 基础位移分量数；逐景附加参数数（τ1, τ2, wx, wy）
VERT = [2, 5, 8, 11]      # 各腿竖向分量列


@dataclass
class Epoch:
    t: float                       # 日序
    geom: int                      # 几何编号
    ps: np.ndarray                 # 候选索引
    Hb: np.ndarray                 # (k,12)
    HT: np.ndarray                 # (k,2) τ1、τ2 列
    Hw: np.ndarray                 # (k,2)
    d: np.ndarray = None           # (k,) 观测 m（相对参考景）
    sig: np.ndarray = None         # (k,) 噪声标准差 m
    prior_tau: np.ndarray = None   # (2,) τ 先验均值
    prior_w: np.ndarray = None     # (2,) 风先验均值


@dataclass
class Options:
    lam_b: float = 3.0             # 二阶差分平滑强度（以 1 mm/(10 d)² 曲率为单位尺度）
    sig_tau: tuple = (2.0, 0.35)   # τ1 ℃；τ2 相对先验的绝对 σ（kW/m²·κ 单位）
    sig_w: float = 15.0            # 风压先验 σ（以 W_UNIT 归一化前的 Pa 计）
    sig_h: float = 0.004           # 水平基础位移零均值先验 σ m（弱可观测，按交底书“冻结/约束水平”）
    use_solar: bool = True
    estimate_wind: bool = True
    w_unit: float = 100.0
    vert: tuple = tuple(VERT)      # 不施加水平先验的列（基础竖向，或刚体模型的 tz/ωx/ωy）
    compute_cond: bool = False


@dataclass
class Result:
    times: np.ndarray
    b: np.ndarray                  # (nt,12)
    b_std: np.ndarray              # (nt,12)
    tau: np.ndarray                # (nt,2)
    w: np.ndarray                  # (nt,2)
    resid_rms: float
    cond: float
    info: dict = field(default_factory=dict)


def invert(epochs: list, ref_index: dict, opt: Options = Options()) -> Result:
    """ref_index[g] = 参考景在 epochs 中的下标。返回所有景时刻的参数估计。"""
    ne = len(epochs)
    NB = epochs[0].Hb.shape[1]
    times = np.array([e.t for e in epochs])
    order = np.argsort(times)
    nx = ne * (NB + NP)
    col = lambda i: i * (NB + NP)
    rows, rhs = [], []
    for i, e in enumerate(epochs):
        if i == ref_index[e.geom]:
            continue
        r = ref_index[e.geom]; er = epochs[r]
        # 同一几何内参考景与本景 PS 集一致（持久散射体）
        for k in range(len(e.ps)):
            a = np.zeros(nx)
            a[col(i):col(i) + NB] = e.Hb[k]
            a[col(r):col(r) + NB] -= er.Hb[k]
            if opt.use_solar:
                a[col(i) + NB:col(i) + NB + 2] = e.HT[k]
                a[col(r) + NB:col(r) + NB + 2] -= er.HT[k]
            else:
                a[col(i) + NB] = e.HT[k, 0]; a[col(r) + NB] -= er.HT[k, 0]
            if opt.estimate_wind:
                a[col(i) + NB + 2:col(i) + NB + 4] = e.Hw[k]
                a[col(r) + NB + 2:col(r) + NB + 4] -= er.Hw[k]
            s = e.sig[k]
            rows.append(a / s); rhs.append(e.d[k] / s)
    nobs = len(rows)
    # 先验 / 正则
    def add(a, v, s):
        rows.append(a / s); rhs.append(v / s)
    i0 = order[0]
    for j in range(NB):                                 # 首景基础位移基准为 0
        a = np.zeros(nx); a[col(i0) + j] = 1; add(a, 0.0, 1e-5)
    scale_c = 1e-3 / 10.0 ** 2 / opt.lam_b               # 曲率尺度 m/d²
    for q in range(1, ne - 1):
        im, ic, ip = order[q - 1], order[q], order[q + 1]
        h1 = max(times[ic] - times[im], 0.5); h2 = max(times[ip] - times[ic], 0.5)
        for j in range(NB):
            a = np.zeros(nx)
            a[col(im) + j] = 2 / (h1 * (h1 + h2)); a[col(ic) + j] = -2 / (h1 * h2); a[col(ip) + j] = 2 / (h2 * (h1 + h2))
            add(a, 0.0, scale_c)
    for i, e in enumerate(epochs):
        for j in range(NB):
            if j not in opt.vert:
                a = np.zeros(nx); a[col(i) + j] = 1; add(a, 0.0, opt.sig_h)
        a = np.zeros(nx); a[col(i) + NB] = 1; add(a, e.prior_tau[0], opt.sig_tau[0])
        a = np.zeros(nx); a[col(i) + NB + 1] = 1
        add(a, e.prior_tau[1] if opt.use_solar else 0.0, opt.sig_tau[1] if opt.use_solar else 1e-6)
        for c in range(2):
            a = np.zeros(nx); a[col(i) + NB + 2 + c] = 1
            if opt.estimate_wind:
                add(a, e.prior_w[c] / opt.w_unit, opt.sig_w / opt.w_unit)
            else:
                add(a, 0.0, 1e-6)
    A = np.array(rows); y = np.array(rhs)
    N = A.T @ A
    x = np.linalg.solve(N, A.T @ y)
    C = np.linalg.inv(N)
    res = (A[:nobs] @ x - y[:nobs])
    if opt.compute_cond:
        ev = np.linalg.eigvalsh(N); cond = float(ev[-1] / max(ev[0], 1e-30))
    else:
        cond = float("nan")
    X = x.reshape(ne, NB + NP)
    std = np.sqrt(np.clip(np.diag(C), 0, None)).reshape(ne, NB + NP)
    return Result(times=times, b=X[:, :NB], b_std=std[:, :NB], tau=X[:, NB:NB + 2], w=X[:, NB + 2:] * opt.w_unit,
                  resid_rms=float(np.sqrt(np.mean(res ** 2))), cond=cond,
                  info={"n_obs": nobs, "n_par": nx})


# ------------------------------------------------------------------ S7 倾斜与预警
def foundation_tilt(base_xy: np.ndarray, bz: np.ndarray):
    """四腿竖向位移拟合平面 z = c0 + gx·x + gy·y，返回 (倾斜率 ‰ = |∇|·1000, 翘曲残差 m)。"""
    A = np.c_[np.ones(len(base_xy)), base_xy]
    c, *_ = np.linalg.lstsq(A, bz, rcond=None)
    warp = bz - A @ c
    return float(np.hypot(c[1], c[2]) * 1000.0), warp


def top_tilt(model, b12: np.ndarray, top_node: int | None = None) -> float:
    """由 u = G_b b 正演塔顶水平位移相对塔基中心，倾斜率 ‰。"""
    u = model.Gb @ b12
    U = u.reshape(-1, 6)[:, :3]
    if top_node is None:
        top_node = int(np.argmax(model.X[:, 2]))
    base = np.mean(U[model.base], 0)
    dx = U[top_node, :2] - base[:2]
    return float(np.hypot(*dx) / model.H * 1000.0)


def warning_level(tilt_permille: float, std_permille: float = 0.0, limit: float = 5.0) -> str:
    """按 DL/T 741 塔高 50 m 以上倾斜限值 5‰ 分级，取上置信界（+2σ）。"""
    v = tilt_permille + 2 * std_permille
    if v < 0.5 * limit:
        return "正常"
    if v < 0.8 * limit:
        return "注意"
    if v < limit:
        return "异常"
    return "紧急"


def d_optimal(Hcand: np.ndarray, m: int, R: np.ndarray | None = None, sigma: float = 1.0):
    """S8：贪心 D 最优选点。Hcand (n_cand, p) 每候选一行（或多行打包为 (n_cand, r, p)）。"""
    H = Hcand if Hcand.ndim == 3 else Hcand[:, None, :]
    p = H.shape[2]
    M = (np.eye(p) * 1e-6) if R is None else R.copy()
    chosen = []
    for _ in range(m):
        best, bv = -1, -np.inf
        for c in range(len(H)):
            if c in chosen:
                continue
            v = np.linalg.slogdet(M + H[c].T @ H[c] / sigma ** 2)[1]
            if v > bv:
                best, bv = c, v
        chosen.append(best)
        M = M + H[best].T @ H[best] / sigma ** 2
    return chosen, M
