# -*- coding: utf-8 -*-
"""V1 独立复核：公共物理模型。只读取 00_设计基准/设计基准参数.json，不导入 C 的任何脚本。
单位：SI（m、Pa、N、m3、s、K）。

与 C 的建模区别（刻意独立）：
- 有效体积模量按“柔度叠加”写成：1/β_eff = 油液(β_oil(p,T)) + 未溶解空气(等温) + 缸筒弹性(厚壁筒) [+ 软管]；
  β_oil 计入压力系数 K'（β=β0+K'p）与温度系数；C 用 状态方程 V=m e^{-p/β} + 空气，未计缸筒、温度系数。
- 两腔各自用局部 β_i，热漂移源力 = αΔT(β1A1 − β2A2)，不假定两腔 β 相等。
- 准静态用“力平衡+粘滞—滑移”的显式增量法（线性化柔度，逐步积分），动态用 BDF/LSODA（C 用 Radau）。
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
V1DIR = os.path.dirname(HERE)
SIM = os.path.dirname(V1DIR)
PKG = os.path.dirname(SIM)
DATA = os.path.join(V1DIR, "数据")
os.makedirs(DATA, exist_ok=True)
BASE = json.load(open(os.path.join(PKG, "00_设计基准", "设计基准参数.json"), encoding="utf-8"))

MPa, cm3, mm, um = 1e6, 1e-6, 1e-3, 1e-6
PATM = 101325.0


def params(**ov):
    B = BASE
    tc = B["尾座液压缸26"]
    P = dict(
        beta0=B["油液"]["有效体积模量_锁闭腔_MPa"] * MPa,
        beta_hose=B["油液"]["有效体积模量_含软管_MPa"] * MPa,
        alpha=B["油液"]["体膨胀系数_1_K"],
        rho=B["油液"]["密度_kg_m3"],
        D=tc["缸径"] * mm, d=tc["杆径"] * mm, S=tc["行程"] * mm,
        x=tc["顶紧位置_伸出量_额定"] * mm,
        Vd=B["锁闭容积"]["阀块直装缸体_每腔死容积"] * cm3,
        Vhose=B["锁闭容积"]["常规软管连接_每腔附加容积"] * cm3,
        Fs=tc["静摩擦力_N"], Fc_ratio=0.8,
        Cint=tc["活塞内泄漏系数_cm3_min_MPa"] * cm3 / 60 / MPa,
        km=B["尾座机械刚度"]["k_m_N_um"] / um,
        F0=B["尾座推力"]["F0_额定"], band=0.05,
        ppre=B["预压"]["有杆腔预压压力_p_pre"] * MPa,
        air=0.0,            # 大气压下未溶解空气体积分数
        Kp=0.0,             # 油液体积模量压力系数 dβ/dp（无量纲），矿物油约 10~12
        kT=0.0,             # 体积模量温度系数 1/K（负值），矿物油约 -0.005
        wall=False, Do=83 * mm, E=206e9, nu_s=0.3,   # 缸筒（套筒外壁取 Ø83，假设）
        alpha_steel=0.0,    # 缸体线膨胀（体积 3α），0 表示不计
        Cseat=1e-4 * cm3 / 60 / MPa,
        mass=8.0, cvisc=3000.0,
    )
    P.update(ov)
    P["A1"] = math.pi / 4 * P["D"] ** 2
    P["A2"] = math.pi / 4 * (P["D"] ** 2 - P["d"] ** 2)
    P["p1set"] = (P["F0"] + P["ppre"] * P["A2"]) / P["A1"]
    return P


def vols(P, x=None, hose=False):
    x = P["x"] if x is None else x
    add = P["Vhose"] if hose else 0.0
    return P["A1"] * x + P["Vd"] + add, P["A2"] * (P["S"] - x) + P["Vd"] + add


def wall_compliance(P):
    """厚壁筒（两端封闭）单位体积柔度 (1/V)dV/dp。"""
    a, b = P["D"] / 2, P["Do"] / 2
    return 2.0 / P["E"] * ((b * b + a * a) / (b * b - a * a) + P["nu_s"])


def beta_eff(P, p, dT=0.0, V=1.0, Vh=0.0):
    """腔体总有效体积模量（p 表压）。V 为腔内油总体积，其中 Vh 为软管段（软管按 beta_hose 计其柔度）。"""
    pa = max(p + PATM, 2e4)
    b_oil = (P["beta0"] + P["Kp"] * p) * (1.0 + P["kT"] * dT)
    xa = P["air"] * PATM / pa
    c = (1 - xa) / b_oil + xa / pa
    Vc = V - Vh
    if P["wall"]:
        c_c = c + wall_compliance(P)
    else:
        c_c = c
    ctot = (Vc * c_c + Vh * (1.0 / P["beta_hose"])) / V if Vh > 0 else c_c
    return 1.0 / ctot


def k_oil(P, p1, p2, x=None, dual=True, hose=False, dT=0.0):
    V1, V2 = vols(P, x, hose)
    Vh = P["Vhose"] if hose else 0.0
    b1 = beta_eff(P, p1, dT, V1, Vh)
    b2 = beta_eff(P, p2, dT, V2, Vh)
    k1 = b1 * P["A1"] ** 2 / V1
    k2 = b2 * P["A2"] ** 2 / V2 if dual else 0.0
    return k1, k2, b1, b2


def thermal_coeff(P, p1, p2, x=None, dual=True, hose=False, eps2=0.0):
    """锁闭腔均匀升温 1 K 顶尖推力增量 N/K（Thevenin：源力/(Σk+km)·km）。
    eps2：有杆腔温升比无杆腔少的比例（两腔温度不一致），0 表示同温。"""
    k1, k2, b1, b2 = k_oil(P, p1, p2, x, dual, hose)
    a_eff = P["alpha"] - 3 * P["alpha_steel"]
    src = a_eff * (b1 * P["A1"] - ((1 - eps2) * b2 * P["A2"] if dual else 0.0))
    return src * P["km"] / (k1 + k2 + P["km"]), src


def stiffness(P, p1, p2, x=None, dual=True, hose=False):
    k1, k2, *_ = k_oil(P, p1, p2, x, dual, hose)
    ko = k1 + k2
    return ko * P["km"] / (ko + P["km"])


def dump(name, obj):
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
