# -*- coding: utf-8 -*-
"""V1-1 刚度与热漂移（解析 + 有限差分数值核对），以及非理想因素下的刚度/漂移。"""
import math
from v1_common import params, k_oil, stiffness, thermal_coeff, vols, beta_eff, dump, MPa, um

out = {}


def both(P, label, hose=False):
    p1, p2 = P["p1set"], P["ppre"]
    r = {}
    for dual, nm in ((False, "单腔"), (True, "双腔")):
        pp2 = p2 if dual else 0.0
        p1 = P["p1set"] if dual else P["F0"] / P["A1"]   # 单腔无预压，p1=F0/A1
        K = stiffness(P, p1, pp2, dual=dual, hose=hose) * um
        T, src = thermal_coeff(P, p1, pp2, dual=dual, hose=hose)
        r[nm] = {"K_N_um": K, "热漂移_N_K": T}
    out[label] = r
    return r


# 1 基准（与设计基准推导式同假设：β=1200 恒定、无空气、刚性缸筒）
P = params()
both(P, "基准_理想")


# 1b 数值核对：直接用质量守恒 + 力平衡做有限差分（不用 k=βA²/V 公式）
def fd_check(P, dual):
    """给定顶尖位移源 δ，求解锁闭腔压力与活塞位移（线性小扰动、牛顿迭代）。"""
    V1, V2 = vols(P)
    p1, p2 = P["p1set"], (P["ppre"] if dual else 0.0)
    b = P["beta0"]

    def F_after(delta, dT):
        # 未知量：活塞后退 u；p1 = p1 + b(α dT + A1 u/V1)，p2 = p2 + b(α dT − A2 u/V2)
        lo, hi = -1e-3, 1e-3
        for _ in range(200):
            u = 0.5 * (lo + hi)
            q1 = p1 + b * (P["alpha"] * dT + P["A1"] * u / V1)
            q2 = p2 + b * (P["alpha"] * dT - P["A2"] * u / V2) if dual else 0.0
            Fh = q1 * P["A1"] - q2 * P["A2"]
            Fw = (p1 * P["A1"] - p2 * P["A2"]) + P["km"] * (delta - u)
            if Fh > Fw:
                hi = u
            else:
                lo = u
        return Fw
    F0 = F_after(0, 0)
    return (F_after(1e-6, 0) - F0), (F_after(0, 1.0) - F0)


out["有限差分核对"] = {nm: dict(zip(("K_N_um", "热漂移_N_K"), fd_check(P, d))) for d, nm in ((False, "单腔"), (True, "双腔"))}

# 2 非理想因素逐项与组合
cases = {
    "空气0.5%": dict(air=0.005),
    "空气1%": dict(air=0.01),
    "缸筒弹性(Ø63/Ø83 钢)": dict(wall=True),
    "β压力系数K'=11": dict(Kp=11.0),
    "缸体钢热膨胀(3α_s)": dict(alpha_steel=1.15e-5),
    "β=800": dict(beta0=800 * MPa),
    "β=1600": dict(beta0=1600 * MPa),
    "组合(空气0.5%+缸筒+K'=11+钢膨胀)": dict(air=0.005, wall=True, Kp=11.0, alpha_steel=1.15e-5),
}
for k, ov in cases.items():
    both(params(**ov), k)
both(params(), "含软管(β_hose=800,每腔+60cm3)", hose=True)

# 3 两腔温度不一致（有杆腔温升为无杆腔的 1−ε）
P = params()
out["两腔温差"] = []
for eps in (0.0, 0.1, 0.2, 0.3):
    T, _ = thermal_coeff(P, P["p1set"], P["ppre"], dual=True, eps2=eps)
    out["两腔温差"].append({"ε(有杆腔温升少的比例)": eps, "双腔热漂移_N_K": T})

# 4 温度对 β 的影响（±5 K 内，kT=-0.005/K）
P = params(kT=-0.005)
out["β温度系数"] = []
for dT in (-5, 0, 5):
    k1, k2, b1, b2 = k_oil(P, P["p1set"], P["ppre"], dT=dT)
    ko = k1 + k2
    out["β温度系数"].append({"dT_K": dT, "β1_MPa": b1 / MPa, "K双_N_um": ko * P["km"] / (ko + P["km"]) * um})

# 5 随伸出量（理想 + 空气0.5%）
out["随伸出量"] = []
for xmm in (20, 47.5, 70, 75, 102.5, 130):
    row = {"x_mm": xmm}
    for lab, ov in (("理想", {}), ("空气0.5%", dict(air=0.005))):
        P = params(x=xmm * 1e-3, **ov)
        row[lab + "_K双"] = stiffness(P, P["p1set"], P["ppre"]) * um
        row[lab + "_K单"] = stiffness(P, P["F0"] / P["A1"], 0.0, dual=False) * um
        row[lab + "_漂移双"] = thermal_coeff(P, P["p1set"], P["ppre"])[0]
    out["随伸出量"].append(row)

dump("v1_static", out)
for k, v in out.items():
    print(k, v)
