# -*- coding: utf-8 -*-
"""P2 仿真公共函数：一次检测复压（动态模型+传感器+拐点识别）、调试标定、锁闭压力估计、准静态保压周期模型。"""
import math

import numpy as np
from scipy.optimize import brentq

from params import MPa, cm3, Lmin, kPa, PATM, mu_T, c_omega, p_min_n, n_prog, caps
from event_model import Event
from detect import make_sensor, sample, knee_P

C_LINE_NOM = 13 * cm3 / 1200e6        # 检测容腔液容的设计值（阀块+回转接头+旋转油道 13 cm3，金属通道 1200 MPa）


# ---------------------------------------------------------------- 一次检测复压
def measure(P, cfg, sens, rng, fs=None, det_kw=None, keep=False):
    """运行一次事件并识别拐点。返回 dict（含真值与识别结果）。"""
    c = dict(cfg)
    if "p_cr_sigma" in c:
        sig = c.pop("p_cr_sigma")
        c["p_cr"] = c.get("p_cr", P["p_cr"]) + rng.normal(0, sig)
    E = Event(P, c)
    t, Y, info = E.run()
    fs = P["fs"] if fs is None else fs
    ts, pm, pt = sample(E, info, sens, fs, rng)
    k = knee_P(ts, pm, P, E.c["p_red"], **(det_kw or {}))
    out = dict(k=k, info=info, p_c0=E.c["p_c0"], p_u0=E.c["p_u0"], p_red=E.c["p_red"], cfg=c,
               F_bar0=info["F_bar_0"])
    if keep:
        out.update(E=E, t=t, Y=Y, ts=ts, pm=pm, pt=pt)
    return out


# ---------------------------------------------------------------- 标定与估计
def visc_ratio(P, T):
    return mu_T(P, T) / mu_T(P, 40.0)


def q_sched(P, T_meas, q_net=None):
    """按油温确定限流流量：Q_m = 目标净流量 + 额定泄漏系数×(μ40/μ(T))×p_set（泄漏随黏度反比变化）。"""
    q_net = P["Q_net_target"] if q_net is None else q_net
    return q_net + P["G_rot40"] / visc_ratio(P, T_meas) * P["p_set"]


def regressors(P, k, T_meas, mode):
    """开启偏置量回归因子。mode: const | T（油温） | Tp（油温+拐点压力） | flowT（流量与油温）。"""
    if mode == "const":
        return np.array([1.0])
    v = visc_ratio(P, T_meas) - 1.0
    if mode == "T":
        return np.array([1.0, v])
    if mode == "Tp":
        return np.array([1.0, v, (k["p_k"] - P["p_set"]) / MPa])
    q = C_LINE_NOM * k["s1"] / Lmin          # 拐点前升压速率换算的净流量（L/min，设计液容）
    return np.array([1.0, q, q * v])


def calibrate(P, mach, sens, rng, mode="flowT", T_list=(30.0, 50.0), p_list=(1.45, 1.65, 1.85), fs=None):
    """调试标定：主轴静止，在两种油温、三个已知锁闭压力下各做一次检测复压（已知压力由临时旋转测压装置给出），
    最小二乘拟合开启偏置量 b = Σβ_j·X_j。返回系数与残差。"""
    X, yv, rows = [], [], []
    for T in T_list:
        for pc in p_list:
            Tm = T + rng.uniform(-P["T_err"], P["T_err"])
            cfg = dict(mach, T=T, n_rpm=0.0, p_c0=pc * MPa, leak_mult=mach.get("leak_mult_cal", mach.get("leak_mult", 1.0)))
            cfg.pop("leak_mult_cal", None)
            cfg.pop("Q_err_drift", None)
            if P.get("Q_sched", True):
                cfg["Q_m"] = q_sched(P, Tm)
            r = measure(P, cfg, sens, rng, fs=fs)
            if not r["k"]["found"]:
                continue
            X.append(regressors(P, r["k"], Tm, mode))
            yv.append(r["k"]["p_k"] - pc * MPa)
            rows.append(dict(T=T, pc=pc, p_k=r["k"]["p_k"], s1=r["k"]["s1"], s2=r["k"]["s2"]))
    X, yv = np.array(X), np.array(yv)
    if len(yv) == 0:
        return nominal_cal(P)
    if len(yv) < X.shape[1] + 1:
        mode = "const"
        X = np.ones((len(yv), 1))
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    res = yv - X @ beta
    return dict(mode=mode, beta=beta.tolist(), n=len(yv), rms_res=float(np.sqrt(np.mean(res ** 2))) if len(yv) else None,
                rows=rows)


def estimate(P, k, T_meas, n_rpm, cal, cw_err=0.0, centrifugal=True):
    """锁闭压力估计：p̂ = p_k − b(X) + c_ω·n²。"""
    if not k["found"]:
        return None
    b = float(np.dot(cal["beta"], regressors(P, k, T_meas, cal["mode"])))
    cw = c_omega(P) * (1 + cw_err) if centrifugal else 0.0
    return k["p_k"] - b + cw * n_rpm ** 2


def nominal_cal(P):
    """未标定：开启偏置量取设计值（单向阀样本开启压差 + 设计流量项估算）。"""
    R40 = 128 * mu_T(P, 40.0) * P["L_path"] / (math.pi * P["d_path"] ** 4)
    q_net = P["Q_net_target"]
    x = q_net / (P["Cd"] * math.pi * P["d_seat"] * math.sin(P["half_cone"]) * math.sqrt(2 * P["p_cr"] / P["rho"]))
    b = P["p_cr"] + R40 * q_net + P["k_spr"] * x / P["A_seat"]
    return dict(mode="const", beta=[b], n=0, rms_res=None, rows=[])


# ---------------------------------------------------------------- 准静态保压周期模型（秒级）
class Hold:
    """锁闭期间夹紧腔 c、松开腔 u 与机构的准静态平衡：油液按含气状态方程，内泄漏 c→u，阀座泄漏，油温漂移。"""

    def __init__(self, P, k_mech=None, C_int=None, air=None):
        self.P = P
        self.km = P["k_mech"] if k_mech is None else k_mech
        self.Ci = P["C_int"] if C_int is None else C_int
        self.air = P["air_frac"] if air is None else air
        self.beta = P["beta_lock"]
        self.T = 0.0              # 相对标定时刻的油温增量 K

    def occ(self, m, p, T):
        P = self.P
        oil = m * (1 + P["alpha_v"] * T) * math.exp(-p / self.beta)
        air = self.air * m * (PATM / (p + PATM))
        return oil + air

    def p_of(self, m, V, T):
        lo = -0.09e6
        if self.occ(m, lo, T) <= V:
            return lo
        hi = 50e6
        return brentq(lambda p: self.occ(m, p, T) - V, lo, hi, xtol=0.5)

    def set_state(self, pc, pu, T=None):
        """由压力反求油液质量与活塞位移（机构力 = pc·A2 − pu·A1，以 x=0 对应设定夹紧力）。"""
        P = self.P
        T = self.T if T is None else T
        self.T = T
        F = pc * P["A2"] - pu * P["A1"]
        self.F_ref = P["p_set"] * P["A2"]
        self.x = (F - self.F_ref) / self.km
        Vc, Vu = P["V_c"] + P["A2"] * self.x, P["V_u"] - P["A1"] * self.x
        self.mc = Vc / self.occ(1.0, pc, T)
        self.mu = Vu / self.occ(1.0, pu, T)
        self.pc, self.pu = pc, pu

    def solve(self):
        P = self.P

        def f(x):
            pc = self.p_of(self.mc, P["V_c"] + P["A2"] * x, self.T)
            pu = self.p_of(self.mu, P["V_u"] - P["A1"] * x, self.T)
            return pc * P["A2"] - pu * P["A1"] - self.F_ref - self.km * x
        x0 = self.x
        a, b = x0 - 2e-3, x0 + 2e-3
        self.x = brentq(f, a, b, xtol=1e-10)
        self.pc = self.p_of(self.mc, P["V_c"] + P["A2"] * self.x, self.T)
        self.pu = self.p_of(self.mu, P["V_u"] - P["A1"] * self.x, self.T)
        return self.pc, self.pu

    def step(self, dt, dTdt):
        """推进 dt 秒：内泄漏 c→u（按参考体积质量），阀座泄漏（c→外），油温变化。"""
        P = self.P
        q_int = self.Ci * (self.pc - self.pu) * dt
        q_seat = P["C_seat"] * max(self.pc, 0) * dt
        dm = q_int / self.occ(1.0, self.pc, self.T)
        self.mc -= dm + q_seat / self.occ(1.0, self.pc, self.T)
        self.mu += q_int / self.occ(1.0, self.pu, self.T)
        self.T += dTdt * dt
        return self.solve()

    def force(self):
        P = self.P
        return self.pc * P["A2"] - self.pu * P["A1"]


def grip(P, F_bar, n):
    """有效夹紧力 = i·拉杆力 − 卡爪离心力。"""
    w = 2 * math.pi * n / 60
    return P["i_chuck"] * F_bar - P["n_jaw"] * P["m_jaw"] * P["r_jaw"] * w * w


def p_equiv(P, F_bar):
    """拉杆力折算到夹紧腔压力（松开腔为零时）。"""
    return F_bar / P["A2"]
