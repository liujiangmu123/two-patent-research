# -*- coding: utf-8 -*-
"""V1-3 切削力阶跃响应（独立动态模型，scipy BDF / LSODA，对照 C 的 Radau）。
模型：活塞质量 m（含套筒顶尖），顶尖与活塞之间为机械弹簧 k_m（顶尖端无质量，载荷作用在顶尖）；
锁闭腔压力按局部 β_eff(p) 积分；摩擦用 LuGre 型鬃毛模型（与 C 的 Stribeck+tanh 不同），
σ0 取 1e8 N/m（预滑移刚度），σ1 临界阻尼量级，Fc=0.8Fs，Stribeck 速度 1 mm/s。
M1b 恒压：p1 由三通减压阀保持，按 不灵敏区 + 流量增益 Kq 进/出油（与 C 同假设值，用于对照）。
"""
import math
import numpy as np
from scipy.integrate import solve_ivp
from v1_common import params, vols, beta_eff, dump, MPa, um, cm3

LMIN = 1e-3 / 60


def step(scheme, F, method="BDF", t_end=0.3, Fs=None, sigma0=1e8, rtol=1e-8, **ov):
    P = params(**{"air": 0.005, **ov})
    if Fs is not None:
        P["Fs"] = Fs
    hose = scheme == "M1s"
    if hose:
        P["beta0"] = P["beta_hose"]
    dual = scheme == "M2"
    A1, A2, km, m = P["A1"], P["A2"], P["km"], P["mass"]
    p1s = P["p1set"] if dual else P["F0"] / A1
    p2s = P["ppre"] if dual else 0.0
    Vh = P["Vhose"] if hose else 0.0
    Fs_, Fc = P["Fs"], P["Fc_ratio"] * P["Fs"]
    s1 = 2 * math.sqrt(sigma0 * m) * 0.5 if Fs_ > 0 else 0.0
    db, Kq = 0.05 * MPa, 10 * LMIN / (0.3 * MPa)
    x0 = P["x"]

    def rhs(t, y):
        u, v, p1, p2, z = y          # u：活塞后退量（压缩方向为正）
        V1, V2 = vols(P, x0 - u, hose)
        b1 = beta_eff(P, p1, 0, V1, Vh)
        b2 = beta_eff(P, p2, 0, V2, Vh)
        Fload = P["F0"] + F               # 载荷作用于顶尖（指向尾座）
        # 顶尖无质量：顶尖力 = Fload（弹簧传递），活塞受 Fload
        if Fs_ > 0:
            g = Fc + (Fs_ - Fc) * math.exp(-(v / 1e-3) ** 2)
            dz = v - sigma0 * abs(v) / g * z
            Ff = sigma0 * z + s1 * dz + P["cvisc"] * v
        else:
            dz = 0.0
            Ff = P["cvisc"] * v
        dv = (Fload - (p1 * A1 - p2 * A2) - Ff) / m
        q1 = 0.0
        if scheme == "M1b":
            ps = p1s
            q1 = Kq * (ps - p1) if p1 < ps else (-Kq * (p1 - ps - db) if p1 > ps + db else 0.0)
        dp1 = b1 / V1 * (A1 * v + q1)
        dp2 = b2 / V2 * (-A2 * v) if dual else 0.0
        return [v, dv, dp1, dp2, dz]

    # 初始：摩擦鬃毛零，力平衡
    y0 = [0.0, 0.0, p1s, p2s, 0.0]
    te = np.linspace(0, t_end, 3001)
    sol = solve_ivp(rhs, (0, t_end), y0, method=method, t_eval=te, rtol=rtol, atol=[1e-12, 1e-9, 1.0, 1.0, 1e-12],
                    max_step=2e-4)
    if not sol.success:
        raise RuntimeError(sol.message)
    tip = (sol.y[0] + F / km) / um        # 顶尖位移 = 活塞后退 + 机械弹簧压缩
    return {"终值um": float(tip[-1]), "峰值um": float(tip.max()), "nfev": int(sol.nfev)}


if __name__ == "__main__":
    R = {}
    for s in ("M2", "M2S", "M1s", "M1b"):
        R[s] = {}
        for F in (500, 1000, 2000):
            r = step(s, F)
            R[s][F] = r
        print(s, R[s])
    # 方法对照 + 无摩擦解析
    P = params(air=0.005)
    R["方法对照_M2_1000N"] = {m: step("M2", 1000, method=m) for m in ("BDF", "LSODA", "Radau")}
    R["无摩擦_M2_1000N"] = step("M2", 1000, Fs=0.0)
    print(R["方法对照_M2_1000N"], R["无摩擦_M2_1000N"])
    # 敏感性：空气 1%、缸筒、Fs 300
    R["敏感性_M2_1000N"] = {
        "空气1%+缸筒+K'11": step("M2", 1000, air=0.01, wall=True, Kp=11.0),
        "Fs=300": step("M2", 1000, Fs=300.0),
        "Fs=50": step("M2", 1000, Fs=50.0),
    }
    print(R["敏感性_M2_1000N"])
    dump("v1_dyn", R)
