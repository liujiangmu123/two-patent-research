# -*- coding: utf-8 -*-
"""V1-7 工件热伸长量 ΔL 估算误差（说明书式（4），权利要求 8、21、22；保护范围预案 B8）。
被控对象用 v1_qs 的独立准静态模型（未溶解空气 0.5%，F_s=150 N）；估算器按权利要求 21 的步骤在后处理中实现：
  ΔL = 基值 + (ΔF − k_T·ΔT)/K，ΔF、ΔT 自本次锁闭起算；每次回复动作前把当前 ΔL 记入基值，动作后重设 F_ref、T_ref。
估算器参数两种：①名义值（β=1200、无空气的解析 K、k_T，即说明书表1口径）；②标定值（按含 0.5% 空气的实际 K、k_T，
相当于在试验台上按权利要求 22 标定 K、并标定 k_T）。测量无噪声（确定性），与 C 的“M2_无测量误差”对照。"""
import numpy as np
from v1_qs import simulate, growth
from v1_common import params, stiffness, thermal_coeff, dump


def est_params(air):
    P = params(air=air)
    return stiffness(P, P["p1set"], P["ppre"]), thermal_coeff(P, P["p1set"], P["ppre"])[0]


def estimate(r, K, kT):
    t, Fpre, Fh, T, d = r["t"], r["Fh_pre"], r["Fh"], r["T"], np.array(r["d_um"])
    ev = set(r["events"])
    base, Fref, Tref = 0.0, Fh[0], T[0]
    est = []
    for i in range(len(t)):
        e = base + ((Fpre[i] - Fref) - kT * (T[i] - Tref)) / K
        est.append(e * 1e6)
        if t[i] in ev:
            base, Fref, Tref = e, Fh[i], T[i]
    err = np.array(est) - d
    return {"最大绝对误差um": float(np.max(np.abs(err))), "终值误差um": float(err[-1]), "伸长真值终值um": float(d[-1])}


SC = {
    "C1 伸长57.5um τ5min": dict(delta=growth(57.5, 300), leak_mult=0.0),
    "C2 伸长138um τ10min": dict(delta=growth(138, 600), leak_mult=0.0),
    "C3 油温+0.2K/min": dict(dTdt=0.2 / 60, leak_mult=0.0),
    "C4 油温-0.2K/min": dict(dTdt=-0.2 / 60, leak_mult=0.0),
    "C5 内泄漏×4": dict(leak_mult=4),
    "C6 综合": dict(delta=growth(57.5, 300), dTdt=0.1 / 60),
    "C6 综合_内泄漏×0.1": dict(delta=growth(57.5, 300), dTdt=0.1 / 60, leak_mult=0.1),
    "C7 1h 油温-5K/h": dict(dTdt=-5 / 3600, t_end=3600, dt=1.0),
}
Kn, kTn = est_params(0.0)
Kc, kTc = est_params(0.005)
R = {"估算器参数": {"名义_K_N_um": Kn * 1e-6, "名义_kT_N_K": kTn, "标定_K_N_um": Kc * 1e-6, "标定_kT_N_K": kTc}}
for k, a in SC.items():
    r = simulate("M2", air=0.005, **a)
    R[k] = {"名义参数": estimate(r, Kn, kTn), "标定参数": estimate(r, Kc, kTc), "动作次数": r["n_act"]}
    print(k, R[k])
dump("v1_dL", R)
