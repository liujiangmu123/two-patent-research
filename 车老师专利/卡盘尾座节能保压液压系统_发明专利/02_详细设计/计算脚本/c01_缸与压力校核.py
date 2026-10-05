# -*- coding: utf-8 -*-
"""C01 缸径、压力、流量与稳定性校核 -> 数据/c01_缸与压力校核.json"""
from common import *

E_steel = 2.06e5  # MPa
res = {}

# 1 尾座缸面积与 p1_set
F_list = [2000, 4000, 6000, 8000, 10000, 12000]
rows = []
for F in F_list:
    p1 = p1_set(F)
    rows.append({"F0_N": F, "p1_set_MPa": p1, "p2=p_pre_MPa": p_pre,
                 "两腔压差_MPa": p1 - p_pre})
res["尾座缸面积"] = {"A1_mm2": A1, "A2_mm2": A2, "A_rod_mm2": Ar, "面积比_A1/A2": A1 / A2,
                 "A1-A2_mm2": A1 - A2}
res["p1_set_表"] = rows
pp_list = [0.5, 1.0, 1.5, 2.0, 3.0]
res["p1_set_随p_pre_F0=6000"] = [{"p_pre": q, "p1_set": p1_set(F0, q)} for q in pp_list]

# 2 减压阀入口压差裕量（蓄能器最低压 pmin）
dp_need = 0.5  # MPa，假设：直动三通减压阀稳定调压所需的最小进出口压差（样本未核对）
pmin = acc["最低工作压力_pmin"]
res["减压阀压差裕量"] = {
    "假设_减压阀最小压差_MPa": dp_need,
    "蓄能器最低压_MPa": pmin,
    "F0=12000时p1_set": p1_set(12000),
    "裕量_MPa": pmin - p1_set(12000),
    "满足要求的最大F0_N(按pmin与dp_need)": (pmin - dp_need) * A1 - p_pre * A2,
    "若F0上限保持12000则建议pmin_MPa": p1_set(12000) + dp_need,
}

# 3 尾座最大油缸力与溢流阀
relief = pump["溢流阀5设定"]
res["尾座最大力"] = {"溢流阀5_MPa": relief, "全压无杆腔推力_N(p2=0)": relief * A1,
                  "允许最大油缸力_N": B["尾座推力"]["允许最大油缸力"],
                  "全压推力是否超过允许值": relief * A1 > B["尾座推力"]["允许最大油缸力"],
                  "安全上限1.25F0_N": 1.25 * F0}

# 4 活塞杆稳定性（一端固定一端自由，长度系数 2，自由长按行程+导向 160 mm 取 300 mm，假设）
d = tail["杆径"]; I = math.pi * d ** 4 / 64; L = 300.0
Fcr = math.pi ** 2 * E_steel * I / (2 * L) ** 2
res["活塞杆稳定性"] = {"杆径": d, "计算长度假设_mm": L, "长度系数": 2, "Fcr_N": Fcr,
                    "对允许最大力的安全系数": Fcr / B["尾座推力"]["允许最大油缸力"]}

# 5 卡盘缸
pc = chuck["夹紧压力_额定"]
res["卡盘缸"] = {"A1_mm2": Ac1, "A2_mm2": Ac2, "额定夹紧拉力_N": pc * Ac2,
              "最大油压拉力_N": chuck["最大油压"] * Ac2,
              "使用压力范围对应拉力_N": [chuck["使用压力范围"][0] * Ac2, chuck["使用压力范围"][1] * Ac2]}

# 6 运动流量（按工作循环时间）
v_tail_adv = x_rated / 14.0   # mm/s，尾座前进 14 s 走额定伸出量（假设走满 70 mm）
v_tail_ret = x_rated / 10.0
q_tail_adv = A1 * v_tail_adv * 60 / 1e6  # L/min
q_tail_ret = A2 * v_tail_ret * 60 / 1e6
v_ch = chuck["行程"] / 1.2
q_ch = Ac2 * v_ch * 60 / 1e6
Q_eff = pump["理论流量_L_min"] * pump["容积效率"]
res["运动流量"] = {"尾座前进速度_mm_s": v_tail_adv, "尾座前进流量_L_min": q_tail_adv,
               "尾座后退流量_L_min": q_tail_ret, "卡盘夹紧速度_mm_s": v_ch, "卡盘夹紧流量_L_min": q_ch,
               "泵有效流量_L_min": Q_eff, "最大需求/泵有效流量": max(q_tail_adv, q_tail_ret, q_ch) / Q_eff,
               "说明": "动作流量远小于泵流量，泵 4 cc/rev 有余量；原设计 25 L/min 泵过大"}

# 7 泵功率校核
p_sys = relief
P_in = p_sys * pump["理论流量_L_min"] / 60 / pump["总效率"]
res["泵电机"] = {"全流量溢流时输入功率_kW": P_in, "电机_kW": pump["电机_kW"], "裕量系数": pump["电机_kW"] / P_in}

dump("c01_缸与压力校核.json", res, "c01_缸与压力校核.py")
