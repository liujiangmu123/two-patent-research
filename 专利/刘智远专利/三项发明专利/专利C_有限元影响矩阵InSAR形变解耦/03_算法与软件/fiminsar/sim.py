# -*- coding: utf-8 -*-
"""合成场景：真值基础位移 + 日照遮挡热场 + 风 → PS 视线向时序观测（含定位误差、大气、失相干噪声），
以及三种方法（经验热胀阈值单点、刚体倾斜、本发明影响矩阵联合反演）的统一调用。

真值与反演模型刻意不一致（模型误差）：真值热场每杆吸收系数随机 ±20%、遮挡采样 5 点；
反演用名义系数、3 点采样；PS 定位有 ~1 m 误差并经概率关联。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import invert as INV
from . import scatter as SC
from . import thermal as TH
from .model import T_REF, W_UNIT, TowerModel

KAPPA = 0.024          # K /(W/m²)：1000 W/m² 全照面时温升约 12 K（阳面肢）


@dataclass
class Epochs:
    """与场景无关的几何/气象/热基缓存（所有 Monte Carlo 共用）。"""
    geoms: list
    t: np.ndarray                  # (ne,)
    gi: np.ndarray                 # (ne,) 几何编号
    Tair: np.ndarray
    I: np.ndarray                  # 辐照 W/m²
    psi2_model: np.ndarray         # (ne, M) 反演模型日照分布（单位辐照 1 kW/m²）
    GT2_model: np.ndarray          # (ne, ndof)
    dT_true: np.ndarray            # (ne, M) 真值杆件温升（相对 T_REF）
    u_th_true: np.ndarray          # (ne, ndof)
    wind: np.ndarray               # (ne, 2) Pa（x,y）


def build_epochs(model: TowerModel, sat: str = "FC1", n_per_geom: int = 34, seed: int = 0,
                 start_day: float = 60.0) -> Epochs:
    rng = np.random.default_rng(seed)
    geoms = SC.geometries(sat)
    normals = TH.angle_leg_normals(model)
    kap_member = KAPPA * (1 + 0.2 * rng.uniform(-1, 1, model.g.n_members))
    ts, gis, Ta, Ir, psi_m, GT2, dTt, uth, wind = [], [], [], [], [], [], [], [], []
    for gi, gm in enumerate(geoms):
        for n in range(n_per_geom):
            day = start_day + gm.offset_day + n * gm.revisit
            sun = TH.sun_vector(day % 365, gm.hour)
            I = TH.irradiance(sun) * rng.uniform(0.35, 1.0)        # 云量
            Tair = TH.air_temperature(day % 365, gm.hour) + rng.normal(0, 2.0)
            eta_m = TH.shadow_fraction(model, sun, n_samp=3)
            eta_t = TH.shadow_fraction(model, sun, n_samp=5)
            psi_model = TH.solar_term(model, sun, normals, eta_m)
            psi_true = TH.solar_term(model, sun, normals, eta_t)
            dT = (Tair - T_REF) + kap_member * I * psi_true
            ts.append(day); gis.append(gi); Ta.append(Tair); Ir.append(I)
            psi_m.append(psi_model); dTt.append(dT)
            GT2.append(model.thermal_column(psi_model))
            uth.append(model.thermal_column(dT))
            ang = rng.uniform(0, 2 * np.pi)
            wind.append(rng.gamma(2.0, 12.0) * np.array([np.cos(ang), np.sin(ang)]))
    return Epochs(geoms, np.array(ts), np.array(gis), np.array(Ta), np.array(Ir), np.array(psi_m),
                  np.array(GT2), np.array(dTt), np.array(uth), np.array(wind))


# ------------------------------------------------------------------ 真值基础位移
def settlement_truth(t: np.ndarray, legs_mm=(-12.0, -3.0, -1.0, -2.0), onset=150.0, width=40.0,
                     horiz_mm=0.8, rng=None) -> np.ndarray:
    """(ne,12)：各腿竖向 S 形沉降（终值 legs_mm）+ 小幅水平位移（m）。"""
    rng = rng or np.random.default_rng(0)
    s = 1 / (1 + np.exp(-(t - onset) / width))
    s = s - s.min()
    s /= max(s.max(), 1e-9)
    B = np.zeros((len(t), 12))
    for L in range(4):
        B[:, 3 * L + 2] = legs_mm[L] * 1e-3 * s
        B[:, 3 * L:3 * L + 2] = rng.normal(0, horiz_mm * 1e-3, 2) * s[:, None]
    return B


@dataclass
class Scenario:
    B: np.ndarray                  # (ne,12) 真值
    n_ps: int = 12                 # 每几何自然 PS 数（不含 CR）
    noise: float = 1.0             # 噪声倍率
    with_cr: bool = True
    pos_sigma: float = 1.0         # PS 三维定位误差 m
    seed: int = 1
    decor_frac: float = 0.05       # 失相干（粗差）比例
    data: dict = field(default_factory=dict)


def synthesize(model: TowerModel, ep: Epochs, sc: Scenario):
    """生成观测，并按“本发明”关联结果组装每景观测算子。返回 dict（含 Epoch 列表、真值分量）。"""
    rng = np.random.default_rng(sc.seed)
    cands = SC.candidates(model, with_cr=sc.with_cr)
    ne = len(ep.t)
    out = {"epochs": [], "ref": {}, "th_true": [], "th_ref": {}, "cands": cands, "assoc": {}}
    Ub_true = ep.u_th_true
    for gi, gm in enumerate(ep.geoms):
        idx = np.where(ep.gi == gi)[0]
        ps = SC.select_ps(cands, gm, sc.n_ps, rng)
        true_xyz = np.array([model.m.X[cands[k].node] + cands[k].offset for k in ps])
        meas_xyz = true_xyz + rng.normal(0, sc.pos_sigma, true_xyz.shape) * np.array([1, 1, 1.2])
        for j, k in enumerate(ps):
            if cands[k].kind == "CR":
                meas_xyz[j] = true_xyz[j] + rng.normal(0, 0.1, 3)        # CR 位置由夹持基准已知
        asc, prob = SC.associate(meas_xyz, cands, gm, model)
        keep = asc >= 0
        out["assoc"][gm.name] = {"n_ps": len(ps), "n_kept": int(keep.sum()),
                                 "correct": int(np.sum(asc[keep] == np.array(ps)[keep]))}
        ps_true = np.array(ps)[keep]; ps_ass = asc[keep]
        l = gm.los
        Pt = model.point_rows([cands[k].node for k in ps_true], [cands[k].offset for k in ps_true])
        Pa = model.point_rows([cands[k].node for k in ps_ass], [cands[k].offset for k in ps_ass])
        Lt = np.einsum("c,kcd->kd", l, Pt); La = np.einsum("c,kcd->kd", l, Pa)
        sig = np.array([cands[k].sigma_mm for k in ps_true]) * 1e-3 * sc.noise
        h = model.m.X[[cands[k].node for k in ps_true], 2]
        atm = rng.normal(0, 3e-6, (len(idx), 1)) * h[None, :] + rng.normal(0, 0.8e-3 * sc.noise, (len(idx), 1))
        ref_local = 0
        d_tot = []
        th_true = []
        for q, i in enumerate(idx):
            u = model.Gb @ sc.B[i] + Ub_true[i] + model.Gw @ (ep.wind[i] / W_UNIT)
            th_true.append(Lt @ Ub_true[i])
            e_ = rng.normal(0, 1, len(ps_true)) * sig
            out_ = rng.random(len(ps_true)) < sc.decor_frac
            e_[out_] *= 5.0
            d_tot.append(Lt @ u + atm[q] + e_)
        d_tot = np.array(d_tot); th_true = np.array(th_true)
        d_rel = d_tot - d_tot[ref_local]
        out["ref"][gi] = len(out["epochs"])
        for q, i in enumerate(idx):
            prior_tau = np.array([ep.Tair[i] + rng.normal(0, 1.0) - T_REF,
                                  KAPPA * ep.I[i] * (1 + rng.normal(0, 0.15))])
            prior_w = ep.wind[i] * (1 + rng.normal(0, 0.3, 2))
            E = INV.Epoch(t=ep.t[i], geom=gi, ps=ps_ass, Hb=La @ model.Gb,
                          HT=np.c_[La @ model.GT1, La @ ep.GT2_model[i] * 1000.0 / 1000.0],
                          Hw=La @ model.Gw, d=d_rel[q], sig=sig, prior_tau=prior_tau, prior_w=prior_w)
            E.index = i
            E.th_true_rel = th_true[q] - th_true[0]
            E.h = h; E.los = l; E.kinds = [cands[k].kind for k in ps_ass]
            E.nodes = [cands[k].node for k in ps_ass]
            out["epochs"].append(E)
    return out


# ------------------------------------------------------------------ 三种方法
def method_proposed(model, data, opt=None):
    opt = opt or INV.Options()
    r = INV.invert(data["epochs"], data["ref"], opt)
    th_est = []
    for i, E in enumerate(data["epochs"]):
        r0 = data["epochs"][data["ref"][E.geom]]
        cur = E.HT @ r.tau[i] if opt.use_solar else E.HT[:, 0] * r.tau[i, 0]
        j = data["ref"][E.geom]
        ref = r0.HT @ r.tau[j] if opt.use_solar else r0.HT[:, 0] * r.tau[j, 0]
        th_est.append(cur - ref)
    return r, th_est


def rigid_basis(model, nodes, los, offsets=None):
    """刚体模型：u = t + ω×(p−c)，c 为塔基中心。返回 (k,6)。"""
    c = np.mean(model.X[model.base], 0)
    out = []
    for q in nodes:
        r = model.X[q] - c
        Bm = np.zeros((3, 6))
        Bm[:, :3] = np.eye(3)
        Bm[:, 3:] = np.array([[0, r[2], -r[1]], [-r[2], 0, r[0]], [r[1], -r[0], 0]])
        out.append(los @ Bm)
    return np.array(out)


def method_rigid(model, data):
    """刚体倾斜 + 均匀线胀（α·z 竖向，经验）模型；各腿沉降由刚体运动在腿底位置求得。"""
    eps = []
    for E in data["epochs"]:
        Hr = rigid_basis(model, E.nodes, E.los)
        hz = 1.2e-5 * model.X[E.nodes, 2] * E.los[2]
        e2 = INV.Epoch(t=E.t, geom=E.geom, ps=E.ps, Hb=Hr, HT=np.c_[hz, np.zeros_like(hz)],
                       Hw=np.zeros((len(hz), 2)), d=E.d, sig=E.sig, prior_tau=E.prior_tau, prior_w=E.prior_w)
        eps.append(e2)
    opt = INV.Options(use_solar=False, estimate_wind=False, vert=(2, 3, 4))
    r = INV.invert(eps, data["ref"], opt)
    c = np.mean(model.X[model.base], 0)
    B = np.zeros((len(eps), 12))
    for L, b in enumerate(model.base):
        rr = model.X[b] - c
        B[:, 3 * L + 2] = r.b[:, 2] + r.b[:, 3] * rr[1] - r.b[:, 4] * rr[0]
        B[:, 3 * L] = r.b[:, 0] + r.b[:, 4] * rr[2] - r.b[:, 5] * rr[1]
        B[:, 3 * L + 1] = r.b[:, 1] + r.b[:, 5] * rr[0] - r.b[:, 3] * rr[2]
    th_est = []
    for i, E in enumerate(eps):
        j = data["ref"][E.geom]
        th_est.append(E.HT[:, 0] * r.tau[i, 0] - eps[j].HT[:, 0] * r.tau[j, 0])
    return B, th_est, r


def method_empirical(model, data, ep: Epochs):
    """现有技术基线：经验热胀阈值（PS 视线向形变 ≈ α·h·ΔT_air·cosθ 扣除）+ 单点形变：
    每腿取最近的塔腿二面角/CR PS，竖向 = d/l_z；某腿在两几何均无 PS 时取其余腿均值。"""
    epochs = data["epochs"]
    ne = len(epochs)
    times = np.array([E.t for E in epochs])
    B = np.full((ne, 12), np.nan)
    th_est = []
    leg_xy = model.X[model.base, :2]
    per_leg = {L: [] for L in range(4)}
    for i, E in enumerate(epochs):
        j = data["ref"][E.geom]
        dT = (E.prior_tau[0]) - (epochs[j].prior_tau[0])
        th = 1.2e-5 * E.h * dT * E.los[2]
        th_est.append(th)
        dc = E.d - th
        for L in range(4):
            cand = [k for k, (kd, nd) in enumerate(zip(E.kinds, E.nodes))
                    if kd in ("leg_dihedral", "CR") and np.linalg.norm(model.X[nd, :2] - leg_xy[L]) < 3.0]
            if cand:
                per_leg[L].append((E.t, float(np.mean(dc[cand]) / E.los[2])))
    for L in range(4):
        if per_leg[L]:
            tt, vv = np.array(per_leg[L]).T
            o = np.argsort(tt)
            B[:, 3 * L + 2] = np.interp(times, tt[o], vv[o])
    vz = B[:, [2, 5, 8, 11]]
    m = np.nanmean(vz, 1) if np.isfinite(vz).any() else np.zeros(ne)
    for L in range(4):
        if not np.isfinite(B[:, 3 * L + 2]).any():
            B[:, 3 * L + 2] = m
    B[:, [0, 1, 3, 4, 6, 7, 9, 10]] = 0.0
    return B, th_est


def thermal_explained(data, th_est):
    num = den = 0.0
    for E, te in zip(data["epochs"], th_est):
        num += np.sum((E.th_true_rel - te) ** 2); den += np.sum(E.th_true_rel ** 2)
    return float(1 - num / den)
