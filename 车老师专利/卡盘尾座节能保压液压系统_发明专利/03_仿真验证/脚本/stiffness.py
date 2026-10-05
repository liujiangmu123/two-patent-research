# -*- coding: utf-8 -*-
"""仿真二：尾座刚度。静刚度随伸出量变化（油柱 + 机械串联，体积模量计入未溶解空气），
动态柔度（线性化：活塞质量 + 粘性阻尼 + 油柱刚度；恒压供油时油柱刚度含减压阀调压动态），
大信号阶跃（tail_dyn 完整模型）。"""
import math
import numpy as np
import hydro as H
import tail_dyn as D
from params import MPa, beta_eff

# 各方案锁闭/供油状态：(无杆腔死容积, 名义体积模量, p1, p2, 有杆腔是否锁闭, 是否恒压供油)
def scheme_state(P, s):
    A1, A2, F0 = P["A1"], P["A2"], P["F0"]
    hose = P["Vd_hose"] + P["Vd_block"]
    if s == "M2":
        return dict(Vd=P["Vd_block"], beta=P["beta_lock"], p1=P["p1_set"], p2=P["p_pre"], dual=True, cp=False)
    if s == "M2h":
        return dict(Vd=hose, beta=P["beta_hose"], p1=P["p1_set"], p2=P["p_pre"], dual=True, cp=False)
    if s == "M1s":
        return dict(Vd=hose, beta=P["beta_hose"], p1=F0 / A1, p2=0.0, dual=False, cp=False)
    if s == "M2S":
        return dict(Vd=P["Vd_block"], beta=P["beta_lock"], p1=F0 / A1, p2=0.0, dual=False, cp=False)
    if s == "M1":
        pb = P["p_back"]
        return dict(Vd=hose, beta=P["beta_hose"], p1=(F0 + pb * A2) / A1, p2=pb, dual=True, cp=False)
    if s in ("M1b", "M0"):
        return dict(Vd=hose, beta=P["beta_hose"], p1=F0 / A1, p2=0.0, dual=False, cp=True)
    raise KeyError(s)


def k_oil_static(P, s, x):
    st = scheme_state(P, s)
    V1, V2 = H.chamber_volumes(x, P, st["Vd"])
    b1 = beta_eff(st["p1"], st["beta"], P["air_frac"])
    k1 = b1 * P["A1"] ** 2 / V1
    k2 = 0.0
    if st["dual"]:
        b2 = beta_eff(st["p2"], st["beta"], P["air_frac"])
        k2 = b2 * P["A2"] ** 2 / V2
    return k1, k2, st


def K_center(P, s, x):
    """顶尖处静刚度 N/m。恒压供油（M0/M1b）超出减压阀不灵敏区后低频刚度趋于 0，此处给出不灵敏区内的小信号值。"""
    k1, k2, st = k_oil_static(P, s, x)
    ko = k1 + k2
    return ko * P["k_m"] / (ko + P["k_m"]), ko


def compliance_frf(P, s, f, x=None):
    """顶尖处动柔度 |C(jω)|（m/N）。恒压供油：k_h(s)=k1·s(1+τs)/(s(1+τs)+ωc)，ωc=β·Kq/V。"""
    x = P["x_nom"] if x is None else x
    k1, k2, st = k_oil_static(P, s, x)
    w = 2 * np.pi * np.asarray(f)
    jw = 1j * w
    if st["cp"]:
        V1, _ = H.chamber_volumes(x, P, st["Vd"])
        b1 = beta_eff(st["p1"], st["beta"], P["air_frac"])
        wc = b1 * P["red_Kq"] / V1
        tau = P["red_tau"]
        kh = k1 * jw * (1 + tau * jw) / (jw * (1 + tau * jw) + wc)
    else:
        kh = (k1 + k2) * np.ones_like(jw)
    Zp = P["m_pist"] * jw ** 2 + P["c_visc"] * jw + kh
    C = 1.0 / P["k_m"] + 1.0 / Zp
    return np.abs(C)


def radial_factor(phi_deg=30.0):
    """60° 顶尖（半锥角 30°）简化楔形模型：径向支承刚度 ≈ 轴向刚度 × cot²φ。"""
    return 1.0 / math.tan(math.radians(phi_deg)) ** 2


def step_response(P, s, dF=1000.0, t_end=0.3):
    st = scheme_state(P, s)
    T = D.TailDyn(P, scheme=s, Vd=st["Vd"], beta=st["beta"], dual=st["dual"], p1=st["p1"], p2=st["p2"])
    T.R1_on = st["cp"]
    T.R2_on = False
    T.const_p = st["cp"]
    if st["cp"]:
        T.p_set1 = st["p1"]
    T.dF = lambda t: dF if t > 0.01 else 0.0
    r = T.run(t_end)
    xc = r["x"] - r["x"][0] - (r["Fw"] - r["Fw"][0]) / P["k_m"]     # 顶尖位移（活塞 + 机械变形）
    return {"t": r["t"], "顶尖位移um": xc * 1e6, "p1": r["p1"], "p2": r["p2"]}


def run(P):
    xs = np.linspace(P["x_range"][0], P["x_range"][1], 23)
    out = {"伸出量mm": (xs * 1e3).tolist(), "静刚度N_um": {}, "油柱刚度N_um": {}}
    for s in ("M2", "M2h", "M2S", "M1", "M1b"):
        Ks, Ko = zip(*[K_center(P, s, x) for x in xs])
        out["静刚度N_um"][s] = [k / 1e6 for k in Ks]
        out["油柱刚度N_um"][s] = [k / 1e6 for k in Ko]
    xn = P["x_nom"]
    nom = {s: K_center(P, s, xn)[0] / 1e6 for s in ("M2", "M2h", "M2S", "M1", "M1b")}
    out["额定伸出量静刚度N_um"] = nom
    out["M2相对M2S提高%"] = 100 * (nom["M2"] / nom["M2S"] - 1)
    out["M2相对M1提高%"] = 100 * (nom["M2"] / nom["M1"] - 1)
    out["M2相对M2h提高%"] = 100 * (nom["M2"] / nom["M2h"] - 1)
    out["说明"] = ("静刚度为顶尖处油柱与机械刚度 k_m 串联值；M1b/M0 为减压阀不灵敏区内小信号值，"
                 "载荷超出不灵敏区（约 ±%.0f N）后低频刚度趋于 0" % (P["red_db"] * P["A1"]))
    f = np.logspace(0, np.log10(1500), 300)
    out["频率Hz"] = f.tolist()
    out["动柔度um_N"] = {s: (compliance_frf(P, s, f) * 1e6).tolist() for s in ("M2", "M2S", "M1", "M1b")}
    out["10Hz动刚度N_um"] = {s: float(1 / compliance_frf(P, s, [10.0])[0] / 1e6) for s in ("M2", "M2S", "M1", "M1b")}
    out["1Hz动刚度N_um"] = {s: float(1 / compliance_frf(P, s, [1.0])[0] / 1e6) for s in ("M2", "M2S", "M1", "M1b")}
    out["径向支承刚度系数cot2phi"] = radial_factor()
    steps = {}
    for s in ("M2", "M2S", "M1", "M1b"):
        r = step_response(P, s)
        steps[s] = {"t": r["t"][::10].tolist(), "顶尖位移um": r["顶尖位移um"][::10].tolist(),
                    "终值um": float(r["顶尖位移um"][-1]), "峰值um": float(np.min(r["顶尖位移um"]))}
    out["1kN阶跃"] = steps
    return out
