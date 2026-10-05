# -*- coding: utf-8 -*-
"""真值结构响应与合成观测。

真值：towerkit 直线塔（真实截面），脉动风（Kaimal + Davenport）抖振力下模态叠加响应；
名义振型基：同一桁架图、PTM 式统一截面（主/斜/辅 L220×22/L140×12/L90×8）的有限元模型——与真值存在模型误差。
像面观测：
  (a) 短片段真实渲染：采样带内按杆件投影宽度绘制带抗锯齿、模糊与噪声的灰度剖面，平移已知亚像素量，
      标定采样带法向位移测量噪声；
  (b) 长时程测量模型：采样带法向位移 = 真值投影法向位移 + 标定噪声 + 相机自振诱导像面运动 + 残余时间偏差。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from . import _tk  # noqa: F401
from towerkit import fem as F
from towerkit import lidar as L
from towerkit import loads as LD
from towerkit import tower as T

PTM_SECTIONS = {"main": "L220x22", "diagonal": "L140x12", "auxiliary": "L90x8"}


@dataclass
class Truth:
    g: object                 # 真值桁架图
    fem: F.FEModel            # 真值有限元
    g_nom: object             # 名义（统一截面）桁架图
    fem_nom: F.FEModel
    t: np.ndarray             # 采样时刻
    q: np.ndarray             # (nt, m) 真值模态坐标
    freq: np.ndarray          # 真值频率
    phi: np.ndarray           # (ndof, m) 真值质量归一化振型
    zeta: np.ndarray
    geom: L.Geometry          # 真值角钢几何（遮挡判断）
    info: dict = None

    def node_disp(self, nodes=None, k0=0, k1=None):
        """返回 (nt, n, 3) 节点平动位移；nodes 给定时只计算这些节点。"""
        n = len(self.g.nodes)
        P = self.phi.reshape(n, 6, -1)[:, :3, :]
        if nodes is not None:
            P = P[np.asarray(nodes)]
        return np.einsum("tm,njm->tnj", self.q[k0:k1], P)


def wind_field_2d(pts, U10=10.0, duration=300.0, dt=0.02, terrain="B", Cy=16.0, Cz=10.0, seed=0, fmax=12.0):
    """二维（横向 y'、高度 z）脉动风场：Kaimal 谱 + Davenport 相干 exp(−f·√(Cy²Δy²+Cz²Δz²)/Ū)，谱表示法。
    pts: (np, 2)。返回 (t, Ū(z) (np,), u' (np, nt))。"""
    rng = np.random.default_rng(seed)
    y, z = pts[:, 0], np.maximum(pts[:, 1], 5.0)
    alpha = {"A": 0.12, "B": 0.15, "C": 0.22, "D": 0.30}[terrain]
    Uz = U10 * (z / 10.0) ** alpha
    Iu = {"A": 0.12, "B": 0.14, "C": 0.23, "D": 0.39}[terrain] * (z / 10.0) ** (-alpha)
    sig = Iu * Uz
    Lu = 100.0 * (z / 30.0) ** 0.5
    nt = int(round(duration / dt))
    t = np.arange(nt) * dt
    df = 1.0 / (nt * dt)
    ks = np.arange(1, min(int(fmax / df), nt // 2))
    Ubar = 0.5 * (Uz[:, None] + Uz[None, :])
    dist = np.sqrt((Cy * (y[:, None] - y[None, :])) ** 2 + (Cz * (z[:, None] - z[None, :])) ** 2)
    npt = len(z)
    spec = np.zeros((npt, nt), complex)
    for k in ks:
        f = k * df
        S = 4 * sig ** 2 * Lu / Uz / (1 + 6 * f * Lu / Uz) ** (5.0 / 3.0)
        Cm = np.sqrt(np.outer(S, S)) * np.exp(-f * dist / Ubar)
        Lc = np.linalg.cholesky(Cm + 1e-10 * np.eye(npt) * S.max())
        spec[:, k] = Lc @ np.exp(1j * rng.uniform(0, 2 * np.pi, npt)) * np.sqrt(2 * df) / 2
    u = np.fft.ifft(spec, axis=1).real * nt * 2
    return t, Uz, u


def band_limited(nt, dt, rms, rng, fc=3.0, n=1):
    """一阶低通整形的高斯过程 (nt, n)，按 rms 归一化。"""
    f = np.fft.rfftfreq(nt, dt)
    H = 1.0 / np.sqrt(1 + (f / fc) ** 2)
    H[0] = 0.0
    x = np.fft.irfft(np.fft.rfft(rng.standard_normal((n, nt)), axis=1) * H, n=nt, axis=1).T
    return x / (x.std(0, keepdims=True) + 1e-30) * rms


def modal_forces(fem, phi, U10, duration, dt, direction, seed, ny=7, nz=14, mu_s=1.3, conductor_rms=None):
    """模态力 P(t) (nt, m)：塔身/横担杆件二维相干抖振力 + 导地线挂点随机动力（沿横担 x、沿线路 y、竖向 z）。
    挂点动力 RMS 默认 (40, 30, 20) N·(U10/10)²，一阶低通 1.5 Hz（导线—绝缘子串系统对高频的滤波）。"""
    if conductor_rms is None:
        conductor_rms = np.array([40.0, 30.0, 20.0]) * (U10 / 10.0) ** 2
    ew = np.asarray(direction, float); ew /= np.linalg.norm(ew)
    el = np.array([-ew[1], ew[0], 0.0])                      # 水平横风向
    X = fem.X
    mid = 0.5 * (X[fem.mi] + X[fem.mj])
    yl = mid @ el
    ygrid = np.linspace(yl.min() - 0.5, yl.max() + 0.5, ny)
    zgrid = np.linspace(1.0, X[:, 2].max() + 0.5, nz)
    YY, ZZ = np.meshgrid(ygrid, zgrid, indexing="ij")
    pts = np.stack([YY.ravel(), ZZ.ravel()], 1)
    t, Uz, u = wind_field_2d(pts, U10, duration, dt, seed=seed)
    nt = len(t)
    m = phi.shape[1]
    G = np.zeros((len(pts), m))
    Ph = phi.reshape(-1, 6, m)[:, :3, :]                      # (n,3,m)
    iy = np.clip(np.searchsorted(ygrid, yl) - 1, 0, ny - 2)
    iz = np.clip(np.searchsorted(zgrid, mid[:, 2]) - 1, 0, nz - 2)
    wy = np.clip((yl - ygrid[iy]) / (ygrid[iy + 1] - ygrid[iy]), 0, 1)
    wz = np.clip((mid[:, 2] - zgrid[iz]) / (zgrid[iz + 1] - zgrid[iz]), 0, 1)
    for e in range(len(fem.L)):
        ex = fem.R[e, 0]
        nv = ew - (ew @ ex) * ex
        a, b = fem.mi[e], fem.mj[e]
        pr = nv @ (Ph[a] + Ph[b])                              # (m,)
        for dy, wyy in ((0, 1 - wy[e]), (1, wy[e])):
            for dz, wzz in ((0, 1 - wz[e]), (1, wz[e])):
                p = (iy[e] + dy) * nz + iz[e] + dz
                c = LD.RHO_AIR * Uz[p] * mu_s * fem.p.b[e] * np.linalg.norm(nv) * fem.L[e] / 2
                G[p] += wyy * wzz * c * pr
    P = u.T @ G
    rng = np.random.default_rng(seed + 1000)
    for a in fem.g.meta.get("attach", []):
        k = 0.35 if a["kind"] == "earthwire" else 1.0
        Fa = band_limited(nt, dt, 1.0, rng, fc=1.5, n=3) * (np.asarray(conductor_rms) * k)[None, :]
        P += Fa @ Ph[a["node"]]
    return t, P


def modal_integrate(P, freq, zeta, dt):
    """各阶 SDOF 状态空间零阶保持精确递推（与 towerkit.fem.modal_response 一致）。"""
    from scipy.linalg import expm
    w = 2 * np.pi * np.asarray(freq)
    nm = len(w)
    Ad = np.zeros((nm, 2, 2)); Bd = np.zeros((nm, 2))
    for r in range(nm):
        Ac = np.array([[0.0, 1.0], [-w[r] ** 2, -2 * zeta[r] * w[r]]])
        Ad[r] = expm(Ac * dt)
        Bd[r] = np.linalg.solve(Ac, (Ad[r] - np.eye(2)) @ np.array([0.0, 1.0]))
    nt = len(P)
    x = np.zeros((nm, 2))
    q = np.zeros((nt, nm))
    for k in range(nt - 1):
        x = np.einsum("rij,rj->ri", Ad, x) + Bd * (0.5 * (P[k] + P[k + 1]))[:, None]
        q[k + 1] = x[:, 0]
    return q


def effective_mass(fem, phi):
    """各阶模态在 x、y 平动与绕 z 扭转方向的有效质量比 (m, 3)。"""
    M = fem.M()
    X = fem.X
    n = len(X)
    fr = ~fem.fixed
    vs = []
    for name in ("x", "y", "rz"):
        v = np.zeros(fem.ndof)
        if name == "x":
            v[0::6] = 1.0
        elif name == "y":
            v[1::6] = 1.0
        else:
            v[0::6] = -X[:, 1]; v[1::6] = X[:, 0]; v[5::6] = 1.0
        v[~fr] = 0.0
        vs.append(v)
    out = np.zeros((phi.shape[1], 3))
    for c, v in enumerate(vs):
        Mv = M @ v
        out[:, c] = (phi.T @ Mv) ** 2 / float(v @ Mv)
    return out


def eval_modes(freq, em, thr=0.02, fmax=8.0):
    """评价模态集：有效质量比（x、y 或扭转）≥ thr 且频率 ≤ fmax 的整体模态（与识别方法无关的客观定义）。"""
    return [int(k) for k in range(len(freq)) if em[k].max() >= thr and freq[k] <= fmax]


def build_truth(preset="suspension", U10=10.0, duration=300.0, fps=50.0, n_modes=20, seed=0,
                direction=(0.6, 0.8, 0.0), stiff_scale=None) -> Truth:
    """真值：真实截面直线塔 + 二维相干脉动风 + 导地线挂点随机动力 → 模态叠加响应。
    stiff_scale：可选 {杆件号: 刚度系数}，用于损伤工况。"""
    spec = T.TowerSpec.preset(preset)
    g = T.build_tower(spec)
    T.assign_sections(g, spec)
    if stiff_scale:
        sc = np.ones(g.n_members)
        for e, v in stiff_scale.items():
            sc[int(e)] = v
        fem = F.FEModel(g, props=F.props_from_graph(g, stiff_scale=sc))
    else:
        fem = F.FEModel(g)
    fem.fix_base()
    g_nom = copy.deepcopy(g)
    g_nom.sec = [PTM_SECTIONS[c] for c in g.cat]
    fem_nom = F.FEModel(g_nom)
    fem_nom.fix_base()
    dt = 1.0 / fps
    rng = np.random.default_rng(seed)
    zeta = np.clip(rng.normal(0.015, 0.004, n_modes), 0.006, 0.03)
    freq, phi = fem.modes(n_modes)
    t, P = modal_forces(fem, phi, U10, duration, dt, direction, seed)
    q = modal_integrate(P, freq, zeta, dt)
    geom = L.build_geometry(g, include_attachments=False)
    em = effective_mass(fem, phi)
    return Truth(g, fem, g_nom, fem_nom, t, q, freq, phi, zeta, geom,
                 info={"U10": U10, "duration": duration, "fps": fps, "direction": list(direction), "seed": seed,
                       "eff_mass": em.tolist(), "eval_modes": eval_modes(freq, em)})


# ====================================================================== (a) 采样带亚像素测量噪声标定
def render_profile(x, center, width, contrast=0.35, bg=0.85, blur=0.7):
    """一维剖面：天空背景上宽 width 像素的暗色杆件（像素积分 + 高斯模糊）。"""
    from scipy.special import erf
    s = np.sqrt(blur ** 2 + 1.0 / 12.0)
    a, b = center - width / 2, center + width / 2
    occ = 0.5 * (erf((x - a) / (np.sqrt(2) * s)) - erf((x - b) / (np.sqrt(2) * s)))
    return bg - contrast * occ


def calibrate_band_noise(method="gradient", widths=(3, 5, 8), band_len=12, n_trials=400, img_noise=0.008,
                         contrast=0.35, seed=0):
    """返回 {width: 单个采样带法向位移噪声标准差（px）}，采样带长 band_len 像素（沿杆件平均）。"""
    from .bands import band_shift_gradient, band_shift_phase
    rng = np.random.default_rng(seed)
    out = {}
    for w in widths:
        half = int(np.ceil(w / 2 + 6))
        x = np.arange(-half, half + 1, dtype=float)
        errs = []
        for _ in range(n_trials):
            c0 = rng.uniform(-0.5, 0.5)
            d = rng.uniform(-1.5, 1.5)
            ref = render_profile(x, c0, w, contrast)[None] + rng.normal(0, img_noise, (band_len, len(x)))
            cur = render_profile(x, c0 + d, w, contrast)[None] + rng.normal(0, img_noise, (band_len, len(x)))
            est = band_shift_gradient(ref, cur) if method == "gradient" else band_shift_phase(ref, cur, w)
            errs.append(est - d)
        e = np.array(errs)
        out[int(w)] = {"std_px": float(np.std(e)), "bias_px": float(np.mean(e)), "rmse_px": float(np.sqrt(np.mean(e ** 2)))}
    return out


# ====================================================================== (b) 长时程测量
def frac_delay(x, tau, dt):
    """频域分数延迟：返回 x(t−tau)。x: (nt, ...)."""
    nt = x.shape[0]
    f = np.fft.rfftfreq(nt, dt)
    X = np.fft.rfft(x, axis=0)
    ph = np.exp(-2j * np.pi * f * tau)
    return np.fft.irfft(X * ph.reshape((-1,) + (1,) * (x.ndim - 1)), n=nt, axis=0)


def measure(A, q_true, sig_px, rng, shake_px=None, tau=0.0, dt=0.02, turb_px=0.0, fc_turb=15.0, chunk=192,
            shake_om=None, shake_gn=None):
    """y(t) = A q(t−τ) + 采样带测量噪声 + 大气湍流到达角抖动（各采样带独立、一阶低通 fc_turb）+ 自振诱导位移。
    A: (n_obs, m)。自振诱导位移可直接给 shake_px (nt, n_obs)，或给转角 shake_om (nt,3) 与法向灵敏度 shake_gn (n_obs,3)
    分块计算。按采样带分块生成以控制内存，返回 float32 (nt, n_obs)。"""
    qd = frac_delay(q_true, tau, dt) if tau else q_true
    nt, n_obs = len(qd), A.shape[0]
    y = np.empty((nt, n_obs), np.float32)
    sig = np.asarray(sig_px, float)
    f = np.fft.rfftfreq(nt, dt)
    Hf = 1.0 / np.sqrt(1 + (f / fc_turb) ** 2)
    Hf[0] = 0.0
    for s in range(0, n_obs, chunk):
        e = min(n_obs, s + chunk)
        blk = qd @ A[s:e].T + rng.standard_normal((nt, e - s)) * sig[None, s:e]
        if turb_px > 0:
            x = np.fft.irfft(np.fft.rfft(rng.standard_normal((e - s, nt)), axis=1) * Hf, n=nt, axis=1).T
            blk += x / (x.std(0, keepdims=True) + 1e-30) * turb_px
        if shake_px is not None:
            blk += shake_px[:, s:e]
        if shake_om is not None:
            blk += shake_om @ shake_gn[s:e].T
        y[:, s:e] = blk
    return y
