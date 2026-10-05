# -*- coding: utf-8 -*-
"""P2 仿真参数：读取 00_设计基准/设计基准参数.json，换算为国际单位制（m、Pa、N、m3、s、K）。
基准未给出的仿真专用假设在本文件中以 assumption 注释列明，并写入报告第 3 节。"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
PKG = os.path.dirname(SIM)
DATA = os.path.join(SIM, "数据")
FIG_R = os.path.join(SIM, "图", "报告")
FIG_P = os.path.join(SIM, "图", "专利附图")
BASE_JSON = os.path.join(PKG, "00_设计基准", "设计基准参数.json")
for d in (DATA, FIG_R, FIG_P):
    os.makedirs(d, exist_ok=True)

MPa, cm3, Lmin, mm, kPa = 1e6, 1e-6, 1e-3 / 60, 1e-3, 1e3
PATM = 0.101325e6
SEED = 20261002


def walther(nu40, nu100):
    """ASTM D341 黏温关系系数 (A, B)：log10 log10(ν+0.7) = A − B·log10(T_K)。"""
    T1, T2 = 313.15, 373.15
    y1, y2 = math.log10(math.log10(nu40 + 0.7)), math.log10(math.log10(nu100 + 0.7))
    B = (y1 - y2) / (math.log10(T2) - math.log10(T1))
    A = y1 + B * math.log10(T1)
    return (A, B)


def nu_of(P, Tc):
    A, B = P["walther_AB"]
    return 10 ** (10 ** (A - B * math.log10(Tc + 273.15))) - 0.7


def load():
    B = json.load(open(BASE_JSON, encoding="utf-8"))
    S, N = B["共用_取自P1"], B["P2新增"]
    oil, cc = S["油液"], S["卡盘液压缸"]
    P = {"_base": B}
    # ---------------- 油液
    P["rho"] = oil["密度_kg_m3"]
    P["nu40"] = oil["运动黏度_40C_cSt"]
    P["walther_AB"] = walther(P["nu40"], 6.8)    # assumption：L-HM46 的 100 ℃ 黏度取 6.8 cSt（黏度指数约 100）
    P["mu40"] = P["rho"] * P["nu40"] * 1e-6
    P["beta_lock"] = oil["有效体积模量_锁闭腔_MPa"] * MPa
    P["beta_hose"] = oil["有效体积模量_含软管_MPa"] * MPa
    P["alpha_v"] = oil["体膨胀系数_1_K"]
    P["air_frac"] = 0.005                        # assumption：大气压下未溶解空气 0.5%（同 P1）
    # ---------------- 卡盘缸（共用）
    P["D_c"], P["d_c"], P["S_c"] = cc["缸径"] * mm, cc["杆径"] * mm, cc["行程"] * mm
    P["A1"] = math.pi / 4 * P["D_c"] ** 2         # 松开腔（无杆腔）
    P["A2"] = math.pi / 4 * (P["D_c"] ** 2 - P["d_c"] ** 2)   # 夹紧腔（有杆腔）
    P["p_set"] = N["复压控制"]["夹紧设定压力_p_set_MPa"] * MPa
    P["p_max_cyl"] = cc["最大油压"] * MPa
    P["G_rot40"] = cc["回转接头泄漏_L_min_at_3MPa"] * Lmin / (3 * MPa)     # 40 ℃ 层流泄漏系数 m3/(s·Pa)
    # ---------------- 回转油缸（P2）
    R = N["回转油缸"]
    P["R_out"], P["R_in"] = R["夹紧腔环形外半径_mm"] * mm, R["夹紧腔环形内半径_mm"] * mm
    P["re2"] = (P["R_out"] ** 2 + P["R_in"] ** 2) / 2      # 环形面积上 r^2 的面积平均
    P["V_c"] = R["夹紧腔锁闭容积_cm3"] * cm3
    P["V_u"] = R["松开腔锁闭容积_cm3"] * cm3
    P["C_int"] = R["活塞内泄漏系数_cm3_min_MPa"] * cm3 / 60 / MPa
    P["C_seat"] = R["单向阀阀座泄漏_cm3_min_MPa"] * cm3 / 60 / MPa
    P["m_pist"] = R["活塞拉杆运动质量_kg"]
    CV = N["内置液控单向阀"]
    P["p_cr"] = CV["开启压差_MPa"] * MPa
    P["d_seat"] = CV["阀座直径_mm"] * mm
    P["A_seat"] = math.pi / 4 * P["d_seat"] ** 2
    P["k_spr"] = CV["弹簧刚度_N_mm"] * 1e3
    P["m_pop"] = CV["阀芯质量_g"] * 1e-3
    P["c_pop"] = CV["阀芯阻尼_N_s_m"]
    P["half_cone"] = math.radians(CV["阀芯半锥角_deg"])
    P["r_cv"] = CV["所在半径_mm"] * mm
    P["p_po"] = CV["松开侧先导开启压力_MPa"] * MPa
    P["V_pp"] = CV["先导活塞排量_cm3"] * cm3
    P["dp_pp"] = CV["先导活塞行程对应压力增量_MPa"] * MPa
    P["sig_cr"] = CV["单次开启压差随机离散_kPa_1sigma"] * kPa
    P["x_pop_max"] = 1.0 * mm                    # assumption：阀芯最大升程 1 mm
    P["Cd"] = 0.62
    # ---------------- 机构
    M = N["卡盘夹紧机构"]
    P["k_mech"] = M["拉杆处等效刚度_kN_mm"] * 1e6
    P["zeta_mech"] = M["机构阻尼比"]
    P["i_chuck"] = M["拉杆力到夹紧力的比值_i"]
    P["n_jaw"], P["m_jaw"], P["r_jaw"] = M["卡爪数"], M["单爪运动质量_kg"], M["卡爪质心半径_mm"] * mm
    P["F_req"] = M["所需最小夹紧力_kN"] * 1e3
    P["n_max"] = M["主轴最高转速_r_min"]
    # ---------------- 回转接头与管路
    L = N["回转接头与管路"]
    P["r_g"] = L["回转接头油槽半径_mm"] * mm
    P["d_hose"], P["L_hose"] = L["软管内径_mm"] * mm, L["软管长度_m"]
    P["beta_h"] = L["软管段有效体积模量_MPa"] * MPa
    P["V_metal"] = L["金属通道容积_cm3"] * cm3
    P["beta_m"] = L["金属通道有效体积模量_MPa"] * MPa
    P["L_path"], P["d_path"] = L["S1至单向阀油道_长度_m"], L["S1至单向阀油道_当量直径_mm"] * mm
    P["V_hose"] = math.pi / 4 * P["d_hose"] ** 2 * P["L_hose"]
    P["V_src"] = 5 * cm3                         # 金属通道中减压阀出口至换向阀 P 口部分（基准说明）
    P["V_rot"] = P["V_metal"] - P["V_src"]       # 回转接头与旋转侧油道
    # ---------------- 复压供油
    Q = N["复压供油"]
    P["Q_m"] = Q["限流流量_Q_m_L_min"] * Lmin
    P["Q_net_target"] = Q["限流目标净流量_L_min"] * Lmin
    P["Q_sched"] = True
    P["dp_fcv"] = Q["调速阀压力补偿最小压差_MPa"] * MPa
    P["tau_fcv"] = Q["调速阀补偿器时间常数_ms"] * 1e-3
    P["pb_red"] = Q["减压阀比例带_MPa"] * MPa
    P["db_rel"] = Q["减压阀二次侧溢流起始超调_MPa"] * MPa
    P["t_dv_delay"], P["t_dv_open"] = Q["换向阀开启延时_ms"] * 1e-3, Q["换向阀开启过渡_ms"] * 1e-3
    P["d_c_ceiling"] = Q["检测上限超出量_Delta_c_MPa"] * MPa
    P["t_hold"] = Q["保持时间_s"]
    P["p_acc"] = 5.5 * MPa                       # 蓄能器工作区间 5~6 MPa 的中值（共用基准）
    P["A_dv"] = 1.5e-5                           # assumption：NG6 换向阀全开等效面积（约 30 L/min@0.5 MPa）
    P["A_bt"] = 1.5e-5                           # assumption：B→T 通路面积
    P["A_uvent"] = 3e-6                          # assumption：松开腔先导单向阀开启后的泄放面积
    # ---------------- 检测
    D = N["检测"]
    P["fs"] = D["采样频率_Hz"]
    P["tau_s"] = D["传感器一阶时间常数_ms"] * 1e-3
    P["FS"] = 10 * MPa
    P["noise"] = D["传感器噪声_FS_1sigma"] * P["FS"]
    P["adc_bits"] = D["ADC位数"]
    P["p_win_lo"] = D["检测窗口下限_MPa"] * MPa
    P["p_win_hi_rel"] = D["检测窗口上限_相对减压阀设定_MPa"] * MPa
    P["slope_ratio_min"] = D["拐点判定斜率比下限"]
    P["guard"] = D["拐点后保护段_ms"] * 1e-3
    P["n_pre"] = D["拐点前拟合段_点数上限"]
    P["t_post"] = D["拐点后拟合段_ms"] * 1e-3
    P["T_err"] = 0.5                              # 油温传感器误差 ±0.5 K
    # ---------------- 复压控制
    C = N["复压控制"]
    P["m_trig"] = C["复压触发裕量_MPa"] * MPa
    P["T_min"], P["T_max"] = C["复压间隔下限_s"], C["复压间隔上限_s"]
    P["ewma"] = 0.5
    P["r_alarm"] = C["泄漏报警_相对额定的压降速率_MPa_min"] * MPa / 60
    # ---------------- 工况
    W = N["工况"]
    P["t_hold_cycle"] = W["保压加工时长_s"]
    P["n_prog"] = W["转速程序"]
    P["dTdt_nom"] = W["油温漂移_额定_K_min"] / 60
    # ---------------- 能耗
    E = S["动力源"]
    P["eta_tot"] = E["总效率"]
    P["eta_motor"] = 0.80                         # assumption（同 P1）
    P["shift_h"], P["shifts_y"], P["price"] = 8, 250, S["工作循环"]["电价_元_kWh"]
    return P


def mu_T(P, Tc):
    return P["rho"] * nu_of(P, Tc) * 1e-6


def G_rot(P, Tc=40.0, mult=1.0):
    """回转接头层流泄漏系数，随黏度反比变化。"""
    return P["G_rot40"] * mult * mu_T(P, 40.0) / mu_T(P, Tc)


def beta_eff(p, beta0, air=0.005, n=1.0):
    """含未溶解空气的有效体积模量（p 为表压，Pa）。"""
    pa = max(p + PATM, 2e4)
    xa = air * (PATM / pa) ** (1.0 / n)
    return 1.0 / ((1 - xa) / beta0 + xa / (n * pa))


def p_min_n(P, n):
    """按主轴转速确定的夹紧压力下限：(F_req + n_jaw·m·r·ω²)/(i·A2)。"""
    w = 2 * math.pi * n / 60
    return (P["F_req"] + P["n_jaw"] * P["m_jaw"] * P["r_jaw"] * w * w) / (P["i_chuck"] * P["A2"])


def c_omega(P):
    """离心油压修正系数（Pa/(r/min)^2）：静止侧拐点读数比夹紧腔面积平均压力低 ρω²(re²−rg²)/2。"""
    return P["rho"] * (2 * math.pi / 60) ** 2 * (P["re2"] - P["r_g"] ** 2) / 2


def n_prog(P, t):
    pts = P["n_prog"]
    for (t0, n0), (t1, n1) in zip(pts[:-1], pts[1:]):
        if t0 <= t <= t1:
            return n0 + (n1 - n0) * (t - t0) / (t1 - t0) if t1 > t0 else n1
    return pts[-1][1]


def caps(P, k_mech=None, beta=None):
    """管路与夹紧腔的液容（m3/Pa）。"""
    km = P["k_mech"] if k_mech is None else k_mech
    b = P["beta_lock"] if beta is None else beta
    C_line = P["V_hose"] / P["beta_h"] + P["V_metal"] / P["beta_m"]
    C_oil = P["V_c"] / b
    C_mech = P["A2"] ** 2 / km if km and km < 1e15 else 0.0
    return C_line, C_oil, C_mech


if __name__ == "__main__":
    P = load()
    Cl, Co, Cm = caps(P)
    print("A1 A2", P["A1"], P["A2"], "re", math.sqrt(P["re2"]))
    print("C_line", Cl, "C_oil", Co, "C_mech", Cm, "ratio", Cl / (Cl + Co + Cm))
    print("G40", P["G_rot40"], "Gp@2MPa L/min", P["G_rot40"] * 2e6 / Lmin)
    print("nu20/40/60", nu_of(P, 20), nu_of(P, 40), nu_of(P, 60))
    print("p_min 0/1500/3000", [p_min_n(P, n) / 1e6 for n in (0, 1500, 3000)])
    print("c_omega*3000^2 kPa", c_omega(P) * 3000 ** 2 / 1e3)
