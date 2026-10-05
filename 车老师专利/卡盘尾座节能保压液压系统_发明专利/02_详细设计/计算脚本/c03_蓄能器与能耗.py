# -*- coding: utf-8 -*-
"""C03 蓄能器容积、保压期间耗油、泵启停间隔、单件循环与年能耗对比 -> 数据/c03_蓄能器与能耗.json

对比方案：
 M0 原系统：CBF-E10 定量泵连续运转、溢流阀 5.0 MPa 溢流保压（课题组 AMESim：1.24 kW）
 M1 小泵 + 电磁卸荷：4 cc/rev 泵连续运转，保压时卸荷 0.3 MPa
 M2 现有间歇保压：蓄能器 + 压力开关、泵间歇，卡盘与尾座经换向滑阀持续接通恒压（CN107559250A 一类）
 M3 本发明：V0 隔离蓄能器、尾座双腔座阀锁闭、卡盘内置液控单向阀锁闭 + 回转接头卸压 + 周期复压、越带才回复
泄漏按层流线性于压差（假设）。
"""
from common import *

c02 = load("c02_刚度与热漂移.json")
R = {}
# ---------- 1 蓄能器 ----------
V0 = acc["容积_L"] * 1e6  # mm3
p0, pmin, pmax = acc["充气压力_p0_20C"], acc["最低工作压力_pmin"], acc["最高工作压力_pmax"]
def usable(n, T_gas=20.0, p0_=p0):
    p0T = (p0_ + P_ATM) * (273.15 + T_gas) / 293.15  # 充气压力随温度
    a, b = pmin + P_ATM, pmax + P_ATM
    if p0T >= a:
        a = p0T  # 低于充气压力部分无油
    return V0 * (p0T / a) ** (1 / n) - V0 * (p0T / b) ** (1 / n)
R["蓄能器"] = {"V0_L": acc["容积_L"], "p0_MPa": p0, "pmin": pmin, "pmax": pmax,
            "可用容积_等温_cm3": usable(1.0) / 1e3, "可用容积_绝热n1.4_cm3": usable(1.4) / 1e3,
            "40C时可用_绝热_cm3": usable(1.4, 40) / 1e3, "0C时可用_绝热_cm3": usable(1.4, 0) / 1e3,
            "p0/pmin": p0 / pmin, "p0/pmin推荐范围": "0.6~0.9（隔膜式，常用经验，pmax/p0 不宜超过 8）",
            "40C时p0T_MPa": (p0 + P_ATM) * 313.15 / 293.15 - P_ATM}
# 改进方案：p0=3.6 MPa（p0/pmin≈0.72，假设推荐值），容积 1.0 L
R["蓄能器_建议p0=3.6"] = {"可用_绝热_cm3": usable(1.4, p0_=3.6) / 1e3, "可用_等温_cm3": usable(1.0, p0_=3.6) / 1e3,
                      "40C可用_绝热_cm3": usable(1.4, 40, 3.6) / 1e3}
dV = usable(1.4) / 1e3  # cm3，按绝热、基准 p0 取保守值
p_acc = (pmin + pmax) / 2

# ---------- 2 保压期间耗油 ----------
c_spool = B["阀"]["滑阀泄漏_每阀_cm3_min_MPa"]      # cm3/min/MPa
c_seat = 1e-4
q_rj = chuck["回转接头泄漏_L_min_at_3MPa"] * 1e3 / 3.0  # cm3/min/MPa
pc = chuck["夹紧压力_额定"]; p1 = p1_set(F0)
c_red = 2.0   # cm3/min/MPa，假设：直动三通减压阀接通时的先导/阀芯泄漏（样本未给，待试验）
# M2：两换向阀 P 口全压，两减压阀接通，回转接头 2 MPa 持续漏，单腔锁闭不适用（恒压）
q_M2 = 2 * c_spool * p_acc + 3 * c_red * p_acc + q_rj * pc
# M3：保压期间 V0 关闭，蓄能器只经 V0 座阀泄漏
q_M3_hold = c_seat * p_acc
# M3 卡盘周期复压：每 T_c 打开 V0、11 换到夹紧位 t_c，回转接头与滑阀漏
T_c, t_c = 60.0, 0.5   # s，假设：复压周期 60 s、每次 0.5 s
V_chuck_event = (q_rj * pc + c_spool * p_acc + c_red * p_acc) * t_c / 60
# M3 尾座越带回复：每次打开 V0、V1、V4 t_r
t_r = 0.3  # s，含座阀开启 50 ms、压力稳定、关闭 50 ms（假设，按基准座阀响应 20~50 ms）
V_tail_fill = 300.0 / c02["双腔预压锁闭_阀块直装"]["泄漏灵敏度_N_per_cm3"]  # 回复 5%F0 所需油量
V_tail_event = V_tail_fill + (2 * c_red * p_acc + c_spool * p_acc) * t_r / 60
T_tail = c02["泄漏推力衰减"]["双腔预压锁闭_座阀"]["越下限时间_min"] * 60  # s 主导：泄漏
q_M3 = q_M3_hold + V_chuck_event / T_c * 60 + V_tail_event / T_tail * 60  # cm3/min
R["保压耗油"] = {"假设_减压阀泄漏_cm3_min_MPa": c_red, "假设_卡盘复压周期_s": T_c, "假设_复压时长_s": t_c,
             "假设_尾座回复时长_s": t_r, "回转接头泄漏系数_cm3_min_MPa": q_rj,
             "M2_耗油_cm3_min": q_M2, "M2_回转接头占比": q_rj * pc / q_M2,
             "M3_卡盘每次复压耗油_cm3": V_chuck_event, "M3_尾座每次回复耗油_cm3": V_tail_event,
             "M3_尾座回复所需充油_cm3": V_tail_fill, "M3_尾座回复间隔_s(泄漏主导)": T_tail,
             "M3_平均耗油_cm3_min": q_M3,
             "M2_泵启动间隔_s": dV / q_M2 * 60, "M3_泵启动间隔_s": dV / q_M3 * 60}

# ---------- 3 循环能耗 ----------
Qth = pump["理论流量_L_min"]; Qe = Qth * pump["容积效率"]; eta = pump["总效率"]
def p_run(p):  # kW，泵在压力 p 下运转输入功率（含电机损耗于总效率）
    return p * Qth / 60 / eta
def charge_E(Vcm3):  # kJ：泵把 Vcm3 充入蓄能器（平均压力）+ 电机空载损耗
    t = Vcm3 / (Qe * 1e3 / 60)
    return (p_run(p_acc) + 0.0) * t, t
cyc = {"夹紧": 1.2, "前进": 14.0, "保压": 600.0, "后退": 10.0, "松开": 0.6, "装卸": 30.0}
T_cyc = sum(cyc.values()); t_move = cyc["夹紧"] + cyc["前进"] + cyc["后退"] + cyc["松开"]
t_idle = cyc["保压"] + cyc["装卸"]
P_unl = pump["卸荷压力"] * Qth / 60 / eta + pump["电机空载损耗_kW"]
E = {}
E["M0"] = 1.24 * T_cyc   # kJ，整循环按 AMESim 保压功率（运动段略低，保守取同值）
E["M1"] = p_run(p_acc) * t_move + P_unl * t_idle
# 动作油量
V_move = (Ac2 * chuck["行程"] + A1 * x_rated + A2 * x_rated + Ac1 * chuck["行程"]) / 1e3  # cm3
def intermittent(q_hold):
    Ec, tc = charge_E(dV)
    n = q_hold * t_idle / 60 / dV
    e_move = p_run(p_acc) * t_move  # 运动期间泵运转（同时补充蓄能器）
    return e_move + n * Ec, n
E["M2"], n2 = intermittent(q_M2)
E["M3"], n3 = intermittent(q_M3)
cycles_year = 8 * 3600 / T_cyc * 250
price = B["工作循环_能耗对比用"]["电价_元_kWh"]
tab = {}
for k, v in E.items():
    kwh = v / 3600
    tab[k] = {"单件能耗_kJ": v, "单件能耗_Wh": kwh * 1e3, "平均功率_W": v / T_cyc * 1e3,
              "年耗电_kWh": kwh * cycles_year, "年电费_元": kwh * cycles_year * price,
              "相对M0节能率": 1 - v / E["M0"]}
R["循环能耗"] = {"循环时间_s": T_cyc, "运动时间_s": t_move, "非运动时间_s": t_idle,
             "年循环数": cycles_year, "卸荷待机功率_kW": P_unl, "运转功率_kW@pacc": p_run(p_acc),
             "单件动作耗油_cm3": V_move, "M2每循环泵启动次数": n2, "M3每循环泵启动次数": n3, "方案": tab,
             "说明": "未计电磁铁线圈功率与控制器；M3 保压期间所有电磁阀断电（常闭座阀、换向阀中位），线圈功耗为零"}

# 敏感性：M3 内泄漏倍数
sens = []
for m in [0.1, 1, 4]:
    q = q_M3_hold + V_chuck_event / T_c * 60 + V_tail_event / (T_tail / m) * 60
    e, n = intermittent(q)
    sens.append({"内泄漏倍数": m, "M3耗油_cm3_min": q, "单件能耗_kJ": e, "节能率": 1 - e / E["M0"]})
R["M3敏感性_内泄漏"] = sens
sens = []
for Tc in [30, 60, 120, 300]:
    q = q_M3_hold + V_chuck_event / Tc * 60 + V_tail_event / T_tail * 60
    e, n = intermittent(q)
    sens.append({"卡盘复压周期_s": Tc, "M3耗油_cm3_min": q, "泵启动间隔_s": dV / q * 60, "单件能耗_kJ": e})
R["M3敏感性_复压周期"] = sens

dump("c03_蓄能器与能耗.json", R, "c03_蓄能器与能耗.py")
