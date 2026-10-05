# -*- coding: utf-8 -*-
"""V1-9 预压压力 p_pre 扫描（额定伸出量 70 mm，未溶解空气 0.5%）：静刚度、热漂移系数、p1set。
用 v1_common 的柔度叠加模型（C 用 stiffness.py 的 beta_eff 状态方程），对照 stiff.json 的 p_pre扫描。"""
from v1_common import params, stiffness, thermal_coeff, dump, MPa, um

R = {"p_pre扫描": []}
for pp in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
    P = params(air=0.005, ppre=pp * MPa)
    K = stiffness(P, P["p1set"], P["ppre"]) * um
    T = thermal_coeff(P, P["p1set"], P["ppre"])[0]
    R["p_pre扫描"].append({"p_pre_MPa": pp, "K_N_um": K, "热漂移_N_K": T, "p1set_MPa": P["p1set"] / MPa})
    print(R["p_pre扫描"][-1])
dump("v1_ppre", R)
