# -*- coding: utf-8 -*-
"""仿真参数：读取 00_设计基准/设计基准参数.json，换算为国际单位制（m、Pa、N、m3、s、K）。
如需修订参数，写 03_仿真验证/数据/params_override.json（扁平键，SI 单位），不改基准文件。
所有标 assumption 的值在报告第 3 节列明。"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)                       # 03_仿真验证
PKG = os.path.dirname(SIM)                        # 包根
DATA = os.path.join(SIM, "数据")
FIG_R = os.path.join(SIM, "图", "报告")
FIG_P = os.path.join(SIM, "图", "专利附图")
BASE_JSON = os.path.join(PKG, "00_设计基准", "设计基准参数.json")
AME_DIR = os.path.join(os.path.dirname(PKG), "新建文件夹")
for d in (DATA, FIG_R, FIG_P):
    os.makedirs(d, exist_ok=True)

MPa, cm3, Lmin, mm, um = 1e6, 1e-6, 1e-3 / 60, 1e-3, 1e-6
PATM = 0.101325e6


def load():
    B = json.load(open(BASE_JSON, encoding="utf-8"))
    oil, tc, cc = B["油液"], B["尾座液压缸26"], B["卡盘液压缸12"]
    P = {}
    # ---------------- 油液
    P["rho"] = oil["密度_kg_m3"]
    P["nu"] = oil["运动黏度_40C_cSt"] * 1e-6
    P["mu"] = P["rho"] * P["nu"]
    P["beta_lock"] = oil["有效体积模量_锁闭腔_MPa"] * MPa
    P["beta_hose"] = oil["有效体积模量_含软管_MPa"] * MPa
    P["alpha_v"] = oil["体膨胀系数_1_K"]
    P["air_frac"] = 0.005          # assumption：大气压下未溶解空气体积分数 0.5%（仅用于低压腔体积模量修正）
    P["poly_air"] = 1.0            # 空气多变指数（慢过程取等温）
    # ---------------- 尾座缸
    P["D_t"], P["d_t"], P["S_t"] = tc["缸径"] * mm, tc["杆径"] * mm, tc["行程"] * mm
    P["A1"] = math.pi / 4 * P["D_t"] ** 2
    P["A2"] = math.pi / 4 * (P["D_t"] ** 2 - P["d_t"] ** 2)
    P["x_nom"] = tc["顶紧位置_伸出量_额定"] * mm
    P["x_range"] = [v * mm for v in tc["顶紧位置范围"]]
    P["Vd_block"] = B["锁闭容积"]["阀块直装缸体_每腔死容积"] * cm3
    P["Vd_hose"] = B["锁闭容积"]["常规软管连接_每腔附加容积"] * cm3
    P["F_s"] = tc["静摩擦力_N"]
    P["F_c"] = 0.8 * tc["静摩擦力_N"]          # assumption：动摩擦取静摩擦的 0.8
    P["c_visc"] = 3000.0                       # assumption：粘性阻尼 N·s/m
    P["m_pist"] = 8.0                          # assumption：活塞+套筒+顶尖运动质量 kg
    P["C_int"] = tc["活塞内泄漏系数_cm3_min_MPa"] * cm3 / 60 / MPa   # m3/(s·Pa)
    P["k_m"] = B["尾座机械刚度"]["k_m_N_um"] / um
    # ---------------- 推力与预压
    TF, PR = B["尾座推力"], B["预压"]
    P["F0"] = TF["F0_额定"]
    P["F0_range"] = TF["F0_可调范围"]
    P["band"] = 0.05                           # F_L=0.95F0，F_H=1.05F0
    P["F_safe"] = 1.25                         # 安全上限系数
    P["p_pre"] = PR["有杆腔预压压力_p_pre"] * MPa
    P["p1_set"] = (P["F0"] + P["p_pre"] * P["A2"]) / P["A1"]
    P["p_back"] = 0.2 * MPa                    # assumption：常规回路回油背压（M1 锁闭时有杆腔初压）
    # ---------------- 卡盘
    P["D_c"], P["d_c"], P["S_c"] = cc["缸径"] * mm, cc["杆径"] * mm, cc["行程"] * mm
    P["A1c"] = math.pi / 4 * P["D_c"] ** 2
    P["A2c"] = math.pi / 4 * (P["D_c"] ** 2 - P["d_c"] ** 2)
    P["p_chuck"] = cc["夹紧压力_额定"] * MPa
    P["C_rot"] = cc["回转接头泄漏_L_min_at_3MPa"] * Lmin / (3 * MPa)   # 回转接头泄漏按层流线性
    P["V_chuck_lock"] = P["A2c"] * P["S_c"] * 0.5 + 40 * cm3          # 夹紧腔锁闭容积（活塞居中+通道）assumption
    P["C_chk"] = 1e-4 * cm3 / 60 / MPa         # 内置单向阀与活塞密封合计泄漏 assumption
    # ---------------- 动力源
    PU, AC = B["动力源"], B["蓄能器8"]
    P["disp"] = PU["排量_cc_rev"] * cm3
    P["n_pump"] = PU["转速_rpm"] / 60
    P["Q_th"] = P["disp"] * P["n_pump"]
    P["eta_v"], P["eta_t"] = PU["容积效率"], PU["总效率"]
    P["eta_motor"] = 0.80                      # assumption：0.75 kW 四极电机效率
    P["P_rated"] = PU["电机_kW"] * 1e3
    P["P_idle"] = PU["电机空载损耗_kW"] * 1e3
    P["p_unload"] = PU["卸荷压力"] * MPa
    P["E_start"] = 0.5 * P["P_rated"]          # assumption：每次起动附加能耗 = 额定功率×0.5 s
    P["p_relief"] = PU["溢流阀5设定"] * MPa
    P["V_acc"] = AC["容积_L"] * 1e-3
    P["p0_acc"] = AC["充气压力_p0_20C"] * MPa
    P["pmin_acc"] = AC["最低工作压力_pmin"] * MPa
    P["pmax_acc"] = AC["最高工作压力_pmax"] * MPa
    P["n_acc"] = 1.4                           # 充液过程（秒级）取绝热；放液（分钟级以上）取等温，见 acc_volume
    # ---------------- 阀
    P["tau_seat"], P["delay_seat"] = 0.010, 0.015      # 座阀：延时 15 ms + 一阶 10 ms（总 ~30 ms，基准 20~50 ms）
    P["Aseat"] = 1.24e-5                       # 座阀全开等效面积：25 L/min @1 MPa、Cd=0.7 assumption
    P["Cd"] = 0.62
    P["C_spool"] = 5.0 * cm3 / 60 / MPa        # 每个 NG6 滑阀 P→T 泄漏
    P["C_red"] = 1.0 * cm3 / 60 / MPa          # 每个直动三通减压阀泄油 assumption
    P["n_spool"], P["n_red"] = 2, 3
    P["red_db"] = 0.05 * MPa                   # 三通减压阀“减压—溢流”之间的不灵敏区 assumption
    P["red_Kq"] = 10 * Lmin / (0.3 * MPa)      # 减压阀流量—压差增益（10 L/min @0.3 MPa）assumption
    P["red_tau"] = 0.02
    P["d_orif"] = 0.2 * mm                     # 方案乙阻尼孔
    P["t_pulse"] = 0.020                       # 方案乙最小脉宽
    # ---------------- 传感与控制
    P["FS_p"] = 10 * MPa
    P["acc_p"] = 0.0025                        # 0.25%FS（最大误差）
    P["noise_p"] = 0.0005                      # 0.05%FS 白噪声（1σ）
    P["dT_sensor"] = 0.1                       # Pt100 系统误差 ±0.1 K
    P["t_filter"] = 0.5                        # 推力滑动平均窗 s
    P["t_min_gap"] = 2.0                       # 两次回复最小间隔 s
    P["t_reset"] = 0.30                        # 方案甲回复开阀时长 s
    # ---------------- 热
    W = B["工件热伸长"]
    P["alpha_w"] = W["线膨胀系数_钢_1_K"]
    P["E_steel"] = 210e9
    # ---------------- 工作循环（s）
    P["cycle"] = {"夹紧": 1.2, "尾座前进": 14.0, "保压加工": 600.0, "尾座后退": 10.0, "松开": 0.6, "装卸": 30.0}
    P["shift_h"], P["shifts_y"], P["price"] = 8, 250, 0.8
    # ---------------- 原系统 M0
    P["M0_Q"] = 14.5 * Lmin
    P["M0_p_crack"] = 5.0 * MPa
    P["M0_grad"] = 20 * Lmin / (0.1 * MPa)     # AMESim RV010 20 L/min/bar
    ov = os.path.join(DATA, "params_override.json")
    if os.path.exists(ov):
        P.update(json.load(open(ov, encoding="utf-8")))
        P["p1_set"] = (P["F0"] + P["p_pre"] * P["A2"]) / P["A1"]
    return P


def beta_eff(p, beta0, air=0.005, n=1.0):
    """含未溶解空气的有效体积模量（p 为表压，Pa）。p 较高时趋近 beta0。"""
    pa = max(p + PATM, 1e3)
    xa = air * (PATM / pa) ** (1.0 / n)
    return 1.0 / ((1 - xa) / beta0 + xa / (n * pa))


if __name__ == "__main__":
    P = load()
    for k in ("A1", "A2", "p1_set", "Q_th", "C_int", "C_rot", "k_m"):
        print(k, P[k])
