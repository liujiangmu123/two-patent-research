# -*- coding: utf-8 -*-
"""V1-8 卡盘夹紧腔锁闭、回转接头卸压与周期复压（独立复算，对照 C 的 chuck.json）。
方法：线性 ODE dp/dt = (β/V)(−C·p + α·V·dT/dt) 的解析解（C 用显式欧拉步进）；
复压耗油 = Σ[(p_set − p_k)·V/β] + 回转接头带压泄漏 C_rot·p_set·t_on（每次 1 s，与 C 同）。
锁闭容积沿用 C 的假设值（有杆腔半行程容积 + 40 cm³ 通道），V1 另给出 ±50% 敏感性。"""
import math
from v1_common import BASE, dump

ch = BASE["卡盘液压缸12"]
oil = BASE["油液"]
beta = oil["有效体积模量_锁闭腔_MPa"]            # MPa
alpha = oil["体膨胀系数_1_K"]
A2 = math.pi / 4 * (ch["缸径"] ** 2 - ch["杆径"] ** 2) / 100      # cm2
V0 = A2 * ch["行程"] / 10 * 0.5 + 40.0                           # cm3（C 的假设）
p_set = ch["夹紧压力_额定"]                                      # MPa
C_chk = 1e-4                                                    # cm3/(min·MPa)，与 C 同
C_rot = ch["回转接头泄漏_L_min_at_3MPa"] * 1000 / 3              # cm3/(min·MPa)


def run(rate_K_min, T_rep, t_end=630.0, V=V0, t_on=1.0):
    """解析：p(t) = p_eq + (p0 − p_eq)·exp(−β C t / V)，p_eq = α V Ṫ / C（C→0 时退化为线性）。"""
    a = beta * C_chk / 60 / V                 # 1/s
    s = beta * alpha * rate_K_min / 60        # MPa/s（温度项）
    n = int(t_end // T_rep)
    pmin, pmax, Vrep = p_set, p_set, 0.0
    for k in range(n):
        p_end = s / a + (p_set - s / a) * math.exp(-a * T_rep) if a > 0 else p_set + s * T_rep
        pmin, pmax = min(pmin, p_end), max(pmax, p_end)
        Vrep += (p_set - p_end) * V / beta + C_rot / 60 * p_set * t_on
    rem = t_end - n * T_rep
    p_end = s / a + (p_set - s / a) * math.exp(-a * rem)
    pmin, pmax = min(pmin, p_end), max(pmax, p_end)
    return {"复压次数": n, "耗油cm3": Vrep, "最低压力MPa": pmin, "最高压力MPa": pmax,
            "最大夹紧力降%": 100 * (1 - pmin / p_set)}


R = {"锁闭容积cm3": V0, "压力—油温系数MPa_K": beta * alpha, "工况": {}}
for nm, r in (("油温降0.2K/min", -0.2), ("油温降0.05K/min", -0.05), ("恒温", 0.0), ("油温升0.2K/min", 0.2)):
    for tr in (30.0, 60.0, 120.0):
        R["工况"][f"{nm}_复压{int(tr)}s"] = run(r, tr)
R["现有技术_回转接头持续带压_630s耗油cm3"] = C_rot * p_set * 630 / 60
for allow in (0.05, 0.10):
    R[f"允许降{int(allow * 100)}%时最长复压间隔s_0.2K/min"] = allow * p_set / (beta * alpha * 0.2 / 60)
R["锁闭容积敏感性_油温降0.2K/min_复压60s"] = {f"V×{m}": run(-0.2, 60.0, V=V0 * m)["最大夹紧力降%"] for m in (0.5, 1.0, 1.5)}
dump("v1_chuck", R)
for k, v in R.items():
    print(k, v)
