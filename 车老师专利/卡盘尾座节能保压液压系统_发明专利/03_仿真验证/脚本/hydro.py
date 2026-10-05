# -*- coding: utf-8 -*-
"""液压基础关系：油液状态方程（含未溶解空气与气穴下限）、孔口流量、蓄能器、解析刚度与热漂移。"""
import math
from scipy.optimize import brentq
from params import PATM

P_VAP = -0.09e6          # 气穴/空气析出压力（表压）下限


def occ_volume(m, p, T, P, beta0):
    """质量 m（以 p=0、T=T0 下的体积计）在压力 p、温升 T 时占据的体积：油液 + 未溶解空气。"""
    oil = m * (1 + P["alpha_v"] * T) * math.exp(-p / beta0)
    air = P["air_frac"] * m * (PATM / (p + PATM)) ** (1.0 / P["poly_air"])
    return oil + air


def pressure(m, V, T, P, beta0):
    """由腔容积 V 反求压力；若 V 大于下限压力对应体积则取气穴压力（腔内出现空穴）。"""
    if occ_volume(m, P_VAP, T, P, beta0) <= V:
        return P_VAP
    hi = 40e6
    while occ_volume(m, hi, T, P, beta0) > V:
        hi *= 2
    return brentq(lambda p: occ_volume(m, p, T, P, beta0) - V, P_VAP, hi, xtol=1.0, rtol=1e-12)


def mass_of(V, p, T, P, beta0):
    """已知容积与压力求腔内油液质量（参考体积）。"""
    return V / occ_volume(1.0, p, T, P, beta0)


def orifice_q(dp, A, P, cd=None):
    """紊流孔口流量（带过零层流过渡，避免数值奇异）。dp>0 为正向。"""
    cd = P["Cd"] if cd is None else cd
    ptr = 0.02e6
    return cd * A * math.sqrt(2.0 / P["rho"]) * dp / math.sqrt(abs(dp) + ptr)


# ---------------------------------------------------------------- 蓄能器
def acc_gas_volume(p, P, n):
    """气腔体积（p 表压）。p0 充气（20 ℃），多变指数 n。"""
    p0a, pa = P["p0_acc"] + PATM, p + PATM
    return P["V_acc"] * (p0a / pa) ** (1.0 / n)


def acc_usable(P, n=1.0):
    return acc_gas_volume(P["pmin_acc"], P, n) - acc_gas_volume(P["pmax_acc"], P, n)


# ---------------------------------------------------------------- 解析刚度与热漂移（设计基准推导式）
def chamber_volumes(x, P, Vd):
    return P["A1"] * x + Vd, P["A2"] * (P["S_t"] - x) + Vd


def k_oil(x, P, Vd, beta1, beta2=None, dual=True):
    beta2 = beta1 if beta2 is None else beta2
    V1, V2 = chamber_volumes(x, P, Vd)
    k1 = beta1 * P["A1"] ** 2 / V1
    k2 = beta2 * P["A2"] ** 2 / V2 if dual else 0.0
    return k1, k2


def K_series(x, P, Vd, beta1, beta2=None, dual=True):
    k1, k2 = k_oil(x, P, Vd, beta1, beta2, dual)
    ko = k1 + k2
    return ko * P["k_m"] / (ko + P["k_m"])


def thermal_N_per_K(x, P, Vd, beta, dual=True):
    """锁闭腔油温均匀升高 1 K 时顶尖推力增量（解析，刚性工件端 + k_m 串联）。"""
    k1, k2 = k_oil(x, P, Vd, beta, beta, dual)
    src = beta * P["alpha_v"] * (P["A1"] - (P["A2"] if dual else 0.0))
    return src * P["k_m"] / (k1 + k2 + P["k_m"])


def growth_N_per_um(x, P, Vd, beta, dual=True):
    """工件热伸长 1 µm 时推力增量（即工件侧刚度）。"""
    return K_series(x, P, Vd, beta, beta, dual) * 1e-6
