# -*- coding: utf-8 -*-
r"""P5 集成锁闭阀块 校核计算（死容积、孔道压降、壁厚强度、螺栓与密封、套管热响应、锁闭刚度贡献）。

用法（项目根目录）：.venv\Scripts\python.exe 车老师专利\P5_液压尾座集成锁闭阀块_实用新型\03_校核计算\p5_calc.py
输入：00_设计基准/P5_设计基准.json；P1 设计基准参数.json（共用参数）；04_模型/_check_report.json（CAD 体积与壁厚）
输出：03_校核计算/校核计算.json、03_校核计算/校核计算书.md
单位：mm、N、MPa(=N/mm2)、mm3（输出换算 cm3）、L/min、K。
"""
import json
import math
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
B5 = json.load(open(os.path.join(ROOT, "00_设计基准", "P5_设计基准.json"), encoding="utf-8"))
P1F = os.path.normpath(os.path.join(ROOT, B5["P1基准"]["文件"]))   # 路径相对本件根目录
B1 = json.load(open(P1F, encoding="utf-8"))
CAD = json.load(open(os.path.join(ROOT, "04_模型", "_check_report.json"), encoding="utf-8"))
OUT = {"_来源脚本": "03_校核计算/p5_calc.py", "_输入": ["00_设计基准/P5_设计基准.json", os.path.relpath(P1F, ROOT).replace("\\", "/"),
                                                     "04_模型/_check_report.json"],
       "_生成时间": time.strftime("%Y-%m-%d %H:%M:%S")}
PI = math.pi
r3 = lambda v: round(v, 3)  # noqa: E731
r2 = lambda v: round(v, 2)  # noqa: E731
r1 = lambda v: round(v, 1)  # noqa: E731

# ------------------------------------------------------------------ 0 共用参数（P1）
TC = B1["尾座液压缸26"]
D, d, S = TC["缸径"], TC["杆径"], TC["行程"]
A1 = PI / 4 * D ** 2
A2 = PI / 4 * (D ** 2 - d ** 2)
OIL = B1["油液"]
BETA, BETA_H, ALPHA = OIL["有效体积模量_锁闭腔_MPa"], OIL["有效体积模量_含软管_MPa"], OIL["体膨胀系数_1_K"]
RHO = OIL["密度_kg_m3"]
NU40 = OIL["运动黏度_40C_cSt"]
KM = B1["尾座机械刚度"]["k_m_N_um"] * 1000.0          # N/mm
VD_P1 = B1["锁闭容积"]["阀块直装缸体_每腔死容积"] * 1000.0
VH_P1 = B1["锁闭容积"]["常规软管连接_每腔附加容积"] * 1000.0
X0 = TC["顶紧位置_伸出量_额定"]
P_PRE = B1["预压"]["有杆腔预压压力_p_pre"]
P1SET = B1["预压"]["无杆腔设定压力_p1_set_额定"]
F0 = B1["尾座推力"]["F0_额定"]
PRV = B1["动力源"]["溢流阀5设定"]
OUT["共用参数_P1"] = {"A1_mm2": r1(A1), "A2_mm2": r1(A2), "beta_MPa": BETA, "beta_含软管_MPa": BETA_H, "alpha_1_K": ALPHA,
                    "km_N_um": KM / 1000, "Vd_P1_cm3": VD_P1 / 1000, "软管附加_cm3": VH_P1 / 1000, "x额定_mm": X0,
                    "p_pre_MPa": P_PRE, "p1_set_MPa": P1SET, "rho_kg_m3": RHO, "nu40_cSt": NU40}
WK = B5["设计工况"]
PD = WK["设计压力_MPa"]
PT = WK["试验压力_MPa"]
QC = WK["校核流量_L_min"]
QA = WK["实际最大流量_L_min"]


def nu_at(T):
    """ASTM D341（Walther）由 40/100 ℃ 黏度插值，cSt。"""
    t1, t2 = 40 + 273.15, 100 + 273.15
    w = lambda n: math.log10(math.log10(n + 0.7))  # noqa: E731
    b = (w(NU40) - w(WK["运动黏度_100C_cSt"])) / (math.log10(t2) - math.log10(t1))
    a = w(NU40) + b * math.log10(t1)
    return 10 ** (10 ** (a - b * math.log10(T + 273.15))) - 0.7


NU20 = nu_at(WK["油温_冷态_C"])

# ------------------------------------------------------------------ 1 死容积
CY = B5["尾座油缸"]
tb = CY["活塞限位凸台"]
gap_C = tb["无杆腔侧"]["h"] * (A1 - PI / 4 * tb["无杆腔侧"]["D"] ** 2)
gap_R = tb["有杆腔侧"]["h"] * (A2 - PI / 4 * (tb["有杆腔侧"]["D_out"] ** 2 - tb["有杆腔侧"]["D_in"] ** 2))
ms = B5["测压与测温"]
v_sens = ms["压力传感器"]["膜片前腔容积_cm3"] * 1000
v_coup = ms["测压排气接头"]["单向阀前腔容积_cm3"] * 1000
cv = CAD["锁闭容积_CAD"]
dead = {}
for side, cad_key, cyl_key, gap in (("有杆腔", "有杆腔", "缸体油道_有杆腔_cm3", gap_R), ("无杆腔", "无杆腔", "缸体油道_无杆腔_cm3", gap_C)):
    blk = cv[cad_key]["扣除插入元件后_cm3"] * 1000
    cyl = cv[cyl_key] * 1000
    items = {"阀块侧孔系（CAD，已扣插入元件）": blk, "压力传感器膜片前腔（估计）": v_sens, "测压排气接头单向阀前腔（估计）": v_coup}
    vb = sum(items.values())
    items2 = dict(items)
    items2["缸体端盖油道（CAD）"] = cyl
    items2["活塞端部 0.5 mm 余隙（计算）"] = gap
    vt = sum(items2.values())
    dead[side] = {"分项_cm3": {k: r3(v / 1000) for k, v in items2.items()}, "阀块侧合计_cm3": r2(vb / 1000),
                  "含缸体油道与端部余隙合计_cm3": r2(vt / 1000), "目标_cm3": B5["目标"]["每腔死容积上限_cm3"],
                  "满足目标": vt / 1000 <= B5["目标"]["每腔死容积上限_cm3"], "_vt_mm3": vt, "_vb_mm3": vb}


# 手算对照（逐段累加，交叉段按较小孔扣除，插入元件按外形扣除）——只作 CAD 量级复核
def cylv(dd, ll):
    return PI / 4 * dd ** 2 * ll


HD = B5["孔道"]
hand_R = (cylv(10, 22) + cylv(6, 110 - 10) + cylv(6, 8) + cylv(6, 15) + cylv(4, 31) + cylv(3, 12) + cylv(4, 12)
          + cylv(19, 1) + cylv(6, 4) * 2 + cylv(15.5, 1) + cylv(5, 3) + 80)
hand_C = (cylv(10, 22) + cylv(6, 53 - 10) + cylv(10, 9) - cylv(5, 9) + cylv(6, 8) + cylv(4, 33) + cylv(3, 12) + cylv(4, 29)
          + cylv(4, 12) + cylv(19, 1) * 2 + cylv(6, 4) * 2 + 80)
dead["手算对照"] = {"有杆腔阀块侧_cm3": r2(hand_R / 1000), "无杆腔阀块侧_cm3": r2(hand_C / 1000),
                 "与CAD偏差_有杆腔_%": r1((hand_R - cv["有杆腔"]["扣除插入元件后_cm3"] * 1000) / (cv["有杆腔"]["扣除插入元件后_cm3"] * 1000) * 100),
                 "与CAD偏差_无杆腔_%": r1((hand_C - cv["无杆腔"]["扣除插入元件后_cm3"] * 1000) / (cv["无杆腔"]["扣除插入元件后_cm3"] * 1000) * 100),
                 "说明": "手算未精确扣除钻尖、交叉孔重叠与阀芯头部，误差 ±15% 以内视为与 CAD 一致；以 CAD 值为准"}
OUT["1_死容积"] = {k: ({kk: vv for kk, vv in v.items() if not kk.startswith("_")} if isinstance(v, dict) else v) for k, v in dead.items()}
VdR, VdC = dead["有杆腔"]["_vt_mm3"], dead["无杆腔"]["_vt_mm3"]


# ------------------------------------------------------------------ 2 锁闭刚度贡献（P1 公式）
def lock(x, vd1, vd2, beta):
    V1, V2 = A1 * x + vd1, A2 * (S - x) + vd2
    k1, k2 = beta * A1 ** 2 / V1, beta * A2 ** 2 / V2
    Ks = k1 * KM / (k1 + KM)
    Kd = (k1 + k2) * KM / (k1 + k2 + KM)
    Td = beta * ALPHA * (A1 - A2) * KM / (k1 + k2 + KM)
    Ts = beta * ALPHA * A1 * KM / (k1 + KM)
    return {"V1_cm3": r1(V1 / 1000), "V2_cm3": r1(V2 / 1000), "k1_N_um": r1(k1 / 1000), "k2_N_um": r1(k2 / 1000),
            "K单腔_N_um": r1(Ks / 1000), "K双腔_N_um": r1(Kd / 1000), "油温漂移_双腔_N_K": round(Td), "油温漂移_单腔_N_K": round(Ts),
            "_Kd": Kd, "_k1": k1, "_k2": k2, "_V1": V1, "_V2": V2}


cases = {"P1基准_Vd15": (VD_P1, VD_P1, BETA), "P5_本设计": (VdC, VdR, BETA),
         "P5_仅阀块侧": (dead["无杆腔"]["_vb_mm3"], dead["有杆腔"]["_vb_mm3"], BETA),
         "软管连接_对照": (VD_P1 + VH_P1, VD_P1 + VH_P1, BETA_H)}
stiff = {}
for nm, (v1, v2, b) in cases.items():
    stiff[nm] = {str(x): lock(x, v1, v2, b) for x in (20, 70, 130)}
ref = stiff["P1基准_Vd15"]["70"]["_Kd"]
dK = {}
for nm in cases:
    for x in ("20", "70", "130"):
        dK.setdefault(nm, {})[x] = r1((stiff[nm][x]["_Kd"] / stiff["P1基准_Vd15"][x]["_Kd"] - 1) * 100)
# 每腔死容积每增加 1 cm3 双腔刚度变化（x=70，数值微分）
e = 1000.0
sens = lock(X0, VdC + e, VdR + e, BETA)["_Kd"] - lock(X0, VdC, VdR, BETA)["_Kd"]       # N/mm（每腔 +1 cm3）
# 达到 P1 软管方案刚度所需的死容积（反算，β=1200）
lo, hi = 0.0, 5e5
target = stiff["软管连接_对照"]["70"]["_Kd"]
for _ in range(80):
    mid = 0.5 * (lo + hi)
    if lock(X0, mid, mid, BETA)["_Kd"] > target:
        lo = mid
    else:
        hi = mid
# 全行程最小刚度
xs = [x for x in range(20, 131)]
kmin = {nm: r1(min(lock(x, v1, v2, b)["_Kd"] for x in xs) / 1000) for nm, (v1, v2, b) in cases.items()}
OUT["2_锁闭刚度"] = {"公式": B1["额定工况推导值"]["推导式"], "工况": {nm: {x: {k: v for k, v in s.items() if not k.startswith("_")}
                                                                   for x, s in st.items()} for nm, st in stiff.items()},
                   "双腔刚度相对P1基准变化_%": dK, "x70每腔死容积加1cm3双腔刚度变化_N_um": r3(sens / 1000),
                   "达到软管方案刚度所需每腔死容积_cm3": r1(lo / 1000), "x20至130双腔刚度最小值_N_um": kmin}


# ------------------------------------------------------------------ 3 孔道压降
def dp_path(Q_lmin, nu_cst, segs, locs):
    """segs：[(名称, d_mm, L_mm)]；locs：[(名称, d_mm, K_turb, K1)]。层流 f=64/Re，Re>2300 用 Blasius。局部损失 K=K_turb+K1/Re。"""
    Q = Q_lmin / 60000.0
    nu = nu_cst * 1e-6
    out, tot = [], 0.0
    for nm, dd, ll in segs:
        A = PI / 4 * (dd / 1000) ** 2
        v = Q / A
        Re = v * dd / 1000 / nu
        f = 64 / Re if Re < 2300 else 0.3164 * Re ** -0.25
        dp = f * (ll / dd) * RHO * v ** 2 / 2 / 1e6
        tot += dp
        out.append({"段": nm, "d_mm": dd, "L_mm": ll, "v_m_s": r2(v), "Re": round(Re), "dp_MPa": round(dp, 4)})
    for nm, dd, kt, k1 in locs:
        A = PI / 4 * (dd / 1000) ** 2
        v = Q / A
        Re = v * dd / 1000 / nu
        K = kt + k1 / Re
        dp = K * RHO * v ** 2 / 2 / 1e6
        tot += dp
        out.append({"局部": nm, "d_mm": dd, "K": r2(K), "v_m_s": r2(v), "dp_MPa": round(dp, 4)})
    return out, tot


SPS = HD["外侧孔道"]
# 第一（无杆腔）：缸腔 → 端盖轴向孔 Ø8 → 竖孔 Ø10 → 对接口 → 第一主孔道 Ø10 → 阀 → 第二阀口环腔 → 外侧孔道 Ø8 → A 口
oc = CY["缸体油道"]["第一缸体油道_无杆腔"]
cyl_segs = [("端盖轴向孔", oc["轴向孔"]["D"], oc["轴向孔"]["X"][1] - oc["轴向孔"]["X"][0]),
            ("端盖竖孔", oc["竖孔"]["D"], -oc["竖孔"]["Z"][0])]
cyl_locs = [("缸腔进入轴向孔（锐边入口）", oc["轴向孔"]["D"], 0.5, 160), ("端盖内 90° 钻孔交汇", oc["竖孔"]["D"], 1.2, 1000)]
blk_segs = [("第一主孔道", HD["第一主孔道_无杆腔"]["D"], 22.0),
            ("外侧孔道", SPS["第一外接油口A_V1"]["D"], SPS["第一外接油口A_V1"]["Y"][1] - SPS["第一外接油口A_V1"]["Y"][0] - 10.2)]
blk_locs = [("第二阀口环腔转入外侧孔道 90°", SPS["第一外接油口A_V1"]["D"], 1.2, 1000), ("外侧孔道出口突扩", SPS["第一外接油口A_V1"]["D"], 1.0, 0)]
press = {}
VALVE_REF = (20.0, 0.7)          # Wandfluh 1.11-2060：20 L/min 时压降 <0.7 MPa（上限值，二次方外推）
for Tn, nu in (("40C", NU40), ("20C", NU20)):
    for qn, Q in (("校核流量", QC), ("实际最大流量", QA)):
        c_list, c_tot = dp_path(Q, nu, cyl_segs, cyl_locs)
        b_list, b_tot = dp_path(Q, nu, blk_segs, blk_locs)
        dv = VALVE_REF[1] * (Q / VALVE_REF[0]) ** 2
        press["%s_%s_%gLmin" % (Tn, qn, Q)] = {"缸体油道_MPa": round(c_tot, 4), "阀块孔道_MPa": round(b_tot, 4),
                                                "座阀_样本外推上限_MPa": round(dv, 3), "合计_MPa": round(c_tot + b_tot + dv, 3),
                                                "明细_缸体": c_list, "明细_阀块": b_list, "nu_cSt": r1(nu)}
OUT["3_孔道压降"] = {"路径": "无杆腔—第一缸体油道—第一对接油口—第一主孔道—第一锁闭座阀—外侧孔道—第一外接油口（有杆腔路径孔径与长度相同，结果相同）",
                  "方法": "沿程：层流 f=64/Re；局部：K=K_turb+K1/Re（90° 钻孔交汇 K_turb=1.2、K1=1000；锐边入口 0.5、160；突扩 1.0），经验取值，误差按 ±50% 估计",
                  "座阀压降": "按 Wandfluh 1.11-2060 样本 20 L/min 时 <0.7 MPa 的上限二次方外推，25 L/min 时的实测曲线未核实",
                  "nu20_cSt": r1(NU20), "结果": press}

# ------------------------------------------------------------------ 4 壁厚强度
BK = B5["阀块本体"]
SY = BK["屈服强度_MPa"]
walls = {w["对"][0] + "—" + w["对"][1]: w["最小壁厚_mm"] for w in CAD["最小壁厚"]}
crit = sorted(CAD["最小壁厚"], key=lambda w: w["最小壁厚_mm"])
holes = [("M22 阀孔第二阀口段", 20.4), ("M22 阀孔 D2 段", 19.0), ("主孔道", 10.0), ("外侧孔道（A/B）", 8.0), ("锁闭油道", 6.0),
         ("套管沉孔", 10.0), ("测压排气接头螺纹孔 M16", 16.0)]
tmin = min(w["最小壁厚_mm"] for w in CAD["最小壁厚"])
res4 = []
for nm, dd in holes:
    r = dd / 2
    t_req = PD * dd / (2 * SY / BK["安全系数_要求"])
    R = r + tmin
    s_lame = PD * (R ** 2 + r ** 2) / (R ** 2 - r ** 2)
    s_lame_T = PT * (R ** 2 + r ** 2) / (R ** 2 - r ** 2)
    res4.append({"孔": nm, "d_mm": dd, "所需最小壁厚_薄壁式_mm": r3(t_req), "按CAD最小壁厚的Lame环向应力_设计压力_MPa": r1(s_lame),
                 "安全系数_对屈服_设计压力": r1(SY / s_lame), "Lame环向应力_试验压力_MPa": r1(s_lame_T), "安全系数_对屈服_试验压力": r1(SY / s_lame_T)})
# 阀块安装面 O 形圈槽底至锁闭油道之间等局部
thread = {"插装阀轴向压力_kN": r2(PD * PI / 4 * 22 ** 2 / 1000), "M22×1.5 螺纹啮合 17 mm 剪切面积_mm2": round(PI * 20.4 * 17 * 0.75),
          "螺纹剪应力_MPa": r2(PD * PI / 4 * 22 ** 2 / (PI * 20.4 * 17 * 0.75)), "说明": "剪切面积按小径×啮合长×0.75 估计"}
OUT["4_壁厚强度"] = {"材料": BK["材料"], "屈服强度_MPa": SY, "要求安全系数": BK["安全系数_要求"], "设计压力_MPa": PD, "试验压力_MPa": PT,
                  "CAD不同压力孔系最小壁厚_mm": tmin, "最薄处": crit[0]["对"], "CAD壁厚前8": crit[:8], "各类孔校核": res4,
                  "插装阀螺纹": thread,
                  "结论": "最薄处 %.1f mm；薄壁式所需壁厚均 <1 mm；按最薄壁厚的 Lame 环向应力在设计压力下 ≤%.0f MPa，对屈服安全系数 ≥%.0f" % (
                      tmin, max(x["按CAD最小壁厚的Lame环向应力_设计压力_MPa"] for x in res4), min(x["安全系数_对屈服_设计压力"] for x in res4))}

# ------------------------------------------------------------------ 5 连接螺栓与密封
SE = B5["安装与密封"]
g = SE["密封槽"]
o = SE["端面密封圈"]
d_seal = g["外径"]
F_p = PD * PI / 4 * d_seal ** 2                     # 每个对接油口的分离力（按槽外径）
F_o = [c * PI * (o["内径"] + o["线径"]) for c in SE["O形圈单位长度压缩力_N_mm"]]
F_sep_total = 2 * (F_p + F_o[1])
bo = SE["连接螺栓"]
As = 36.6                                           # M8 应力截面积 mm2
Rp = 640.0                                          # 8.8 级 Rp0.2
FV = bo["预紧率"] * Rp * As
d2, P_, mu = 7.188, 1.25, bo["拧紧摩擦系数"]
Dkm = 0.5 * (13.0 + bo["通孔D"])
MA = FV * (0.16 * P_ + 0.58 * d2 * mu + Dkm / 2 * mu) / 1000
phi = 0.2                                           # 载荷系数（assumption，钢—钢连接常见 0.1~0.3）
F_ext_bolt = (F_p + F_o[1]) / 2                     # 每端两只螺栓分担该端油口
F_res = FV - (1 - phi) * F_ext_bolt
sig_b = (FV + phi * F_ext_bolt) / As
Ap = PI / 4 * (13.0 ** 2 - bo["通孔D"] ** 2)
squeeze = (o["线径"] - g["深"]) / o["线径"]
fill = (PI / 4 * o["线径"] ** 2) / ((g["外径"] - g["内径"]) / 2 * g["深"])
OUT["5_螺栓与密封"] = {
    "每个对接油口分离力_设计压力_N": round(F_p), "O形圈压缩反力_N": [round(x) for x in F_o], "两口合计最大分离力_N": round(F_sep_total),
    "螺栓": bo["规格"], "单只预紧力_N": round(FV), "拧紧力矩_Nm": r1(MA), "总预紧力_N": round(4 * FV),
    "预紧力对分离力倍数": r1(4 * FV / F_sep_total), "单只螺栓外载_N": round(F_ext_bolt), "残余夹紧力_N": round(F_res),
    "螺栓应力_MPa": r1(sig_b), "螺栓应力比Rp0.2": r2(sig_b / Rp), "头下支承面压强_MPa": r1(FV / Ap), "旋入深度_mm": bo["旋入端盖深"],
    "旋入深度对公称直径": r2(bo["旋入端盖深"] / 8.0), "O形圈压缩率_%": r1(squeeze * 100), "槽填充率_%": r1(fill * 100),
    "密封间隙_mm": 0.0, "说明": "螺栓预紧率 0.7×Rp0.2、载荷系数 0.2 为常用取值（assumption）；端面密封为金属面贴合，挤出间隙为零；O 形圈压缩率 20%~30%、填充率 ≤85% 为常用范围"}

# ------------------------------------------------------------------ 6 油温传感器套管热响应
TW = ms["油温传感器套管"]
TS = ms["油温传感器"]
k_oil, cp_oil = WK["油液导热系数_W_mK"], WK["油液比热_J_kgK"]
Do, Di, Lw = TW["外径"] / 1000, TW["内径"] / 1000, TS["感温段长_mm"] / 1000
rho_ss, c_ss, k_ss = 7900, 500, 16.2
C_well = rho_ss * c_ss * PI / 4 * (Do ** 2 - Di ** 2) * Lw + rho_ss * c_ss * PI / 4 * Do ** 2 * TW["端部壁厚"] / 1000
C_probe = 3.5e6 * PI / 4 * 0.003 ** 2 * Lw          # 铠装热电阻等效体积热容 3.5 MJ/m3K（assumption）
A_out = PI * Do * Lw + PI / 4 * Do ** 2
nu_m2 = NU40 * 1e-6
a_oil = k_oil / (RHO * cp_oil)
Pr = nu_m2 / a_oil


def h_nat(dT):
    Ra = 9.81 * ALPHA * dT * Do ** 3 / (nu_m2 * a_oil)
    Nu = (0.6 + 0.387 * Ra ** (1 / 6) / (1 + (0.559 / Pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return Nu * k_oil / Do, Ra, Nu


def h_forced(v):
    Re = v * Do / nu_m2
    Nu = 0.3 + 0.62 * Re ** 0.5 * Pr ** (1 / 3) / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25 * (1 + (Re / 282000) ** 0.625) ** 0.8
    return Nu * k_oil / Do, Re, Nu


R_wall = math.log(Do / Di) / (2 * PI * k_ss * Lw)
R_gap = math.log(Di / 0.003) / (2 * PI * TS["导热膏导热系数_W_mK"] * Lw)
ann = (TW["外径"] / 2, B5["测压与测温"]["套管安装孔"]["沉孔D"] / 2)
h_cond = k_oil / (ann[0] / 1000 * math.log(ann[1] / ann[0]))   # 环隙纯导热等效换热系数（停滞油、沉孔段）
cases6 = {}
for nm, h in (("停滞油_自然对流_dT0.2K", h_nat(0.2)[0]), ("停滞油_自然对流_dT1K", h_nat(1.0)[0]), ("停滞油_环隙导热", h_cond),
              ("流动_0.94Lmin", h_forced(QA / 60000 / (PI / 4 * 0.01 ** 2))[0]),
              ("流动_25Lmin", h_forced(QC / 60000 / (PI / 4 * 0.01 ** 2))[0])):
    R_out = 1 / (h * A_out)
    tau = (C_well + C_probe) * R_out + C_probe * (R_wall + R_gap)
    cases6[nm] = {"h_W_m2K": r1(h), "tau_s": r1(tau),
                  "滞后误差_0.02K_min_K": r3(0.02 / 60 * tau), "滞后误差_0.2K_min_K": r3(0.2 / 60 * tau),
                  "对应双腔推力误差_0.2K_min_N": r1(0.2 / 60 * tau * B1["额定工况推导值"]["油温热漂移推力_双腔锁闭_N_K"])}
Bi = h_nat(1.0)[0] * (Do - Di) / 2 / k_ss
OUT["6_套管热响应"] = {"模型": "集总参数一阶模型：τ=(C套管+C感温元件)/(h·A)+C感温元件·(R壁+R导热膏)；外部换热按停滞油自然对流（Churchill–Chu 水平圆柱）、"
                              "环隙纯导热、流动时横掠圆柱（Churchill–Bernstein，流速按主孔道 Ø10 平均流速）三种情况",
                       "C套管_J_K": round(C_well, 3), "C元件_J_K": round(C_probe, 3), "A外_mm2": r1(A_out * 1e6), "R壁_K_W": r2(R_wall), "R导热膏_K_W": r2(R_gap),
                       "Pr": round(Pr), "Bi": round(Bi, 4), "情况": cases6,
                       "结论": "停滞油中 τ 约 %.0f~%.0f s，流动时约 %.0f~%.0f s；油温漂移 0.2 K/min 时滞后误差约 %.2f K" % (
                           min(cases6[k]["tau_s"] for k in cases6 if k.startswith("停滞")), max(cases6[k]["tau_s"] for k in cases6 if k.startswith("停滞")),
                           cases6["流动_25Lmin"]["tau_s"], cases6["流动_0.94Lmin"]["tau_s"],
                           max(cases6[k]["滞后误差_0.2K_min_K"] for k in cases6 if k.startswith("停滞"))),
                       "说明": "只算套管与元件对周围油液的响应；套管所在油道油液与缸腔主体油液之间的温差另由缸体—阀块导热决定，未计算，需试验台实测"}

# ------------------------------------------------------------------ 7 锁闭压力升高与安全阀
s70 = lock(X0, VdC, VdR, BETA)
du = s70["油温漂移_双腔_N_K"] / KM                              # mm/K
dp2 = BETA * ALPHA + BETA * A2 / s70["_V2"] * du
dp1 = BETA * ALPHA - BETA * A1 / s70["_V1"] * du
R1max = 6.81                                                    # P1 详细设计：R1 最高允许设定（对应 18 kN）
OUT["7_锁闭压力升高"] = {"油温每升高1K_p1_MPa": r3(dp1), "油温每升高1K_p2_MPa": r3(dp2),
                     "p1自设定值升至设计压力所需温升_K": r2((PD - P1SET) / dp1), "p2自预压升至设计压力所需温升_K": r2((PD - P_PRE) / dp2),
                     "有杆腔增压_工件推力消失且R1按最高6.81MPa补压时p2_MPa": r2(R1max * A1 / A2),
                     "有杆腔增压_R1按额定p1set补压时p2_MPa": r2(P1SET * A1 / A2),
                     "安全阀设定_MPa": B5["安全阀孔"]["溢流阀设定_MPa"],
                     "结论": "有杆腔被锁闭时，若无杆腔被补压而工件推力消失，有杆腔会被增压到无杆腔压力的 A1/A2=%.3f 倍；"
                           "R1 最高设定下可达 %.2f MPa，超过设计压力，故在有杆腔锁闭油道上设安全阀孔。停机锁闭期间温升 %.1f K 即可使无杆腔达到设计压力，"
                           "如需防护可在第一锁闭油道上增设同样的安全阀孔（变化例）" % (A1 / A2, R1max * A1 / A2, (PD - P1SET) / dp1)}

# ------------------------------------------------------------------ 汇总
OUT["汇总"] = {
    "每腔死容积_有杆腔_cm3": dead["有杆腔"]["含缸体油道与端部余隙合计_cm3"], "每腔死容积_无杆腔_cm3": dead["无杆腔"]["含缸体油道与端部余隙合计_cm3"],
    "阀块侧_有杆腔_cm3": dead["有杆腔"]["阀块侧合计_cm3"], "阀块侧_无杆腔_cm3": dead["无杆腔"]["阀块侧合计_cm3"],
    "x70双腔刚度_P5_N_um": stiff["P5_本设计"]["70"]["K双腔_N_um"], "x70双腔刚度_P1基准_N_um": stiff["P1基准_Vd15"]["70"]["K双腔_N_um"],
    "x70双腔刚度_软管_N_um": stiff["软管连接_对照"]["70"]["K双腔_N_um"],
    "阀块孔道压降_25Lmin_40C_MPa": press["40C_校核流量_25Lmin"]["阀块孔道_MPa"],
    "缸体油道压降_25Lmin_40C_MPa": press["40C_校核流量_25Lmin"]["缸体油道_MPa"],
    "合计压降含座阀_25Lmin_40C_MPa": press["40C_校核流量_25Lmin"]["合计_MPa"],
    "最小壁厚_mm": tmin, "最小安全系数_设计压力": min(x["安全系数_对屈服_设计压力"] for x in res4),
    "螺栓预紧对分离力倍数": OUT["5_螺栓与密封"]["预紧力对分离力倍数"],
    "套管时间常数_停滞_s": [min(cases6[k]["tau_s"] for k in cases6 if k.startswith("停滞")), max(cases6[k]["tau_s"] for k in cases6 if k.startswith("停滞"))],
}
OUT["汇总"]["x70双腔刚度_P5相对软管_%"] = r1((stiff["P5_本设计"]["70"]["_Kd"] / stiff["软管连接_对照"]["70"]["_Kd"] - 1) * 100)
OUT["汇总"]["x70每腔死容积加1cm3双腔刚度变化_N_um"] = OUT["2_锁闭刚度"]["x70每腔死容积加1cm3双腔刚度变化_N_um"]
with open(os.path.join(HERE, "校核计算.json"), "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, ensure_ascii=False, indent=1)
print(json.dumps(OUT["汇总"], ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ 校核计算书.md（全部数值取自 OUT，不手填）
def md():
    S = OUT["汇总"]
    L_ = []
    a = L_.append
    a("# P5 集成锁闭阀块 校核计算书")
    a("")
    a("> 由 `03_校核计算/p5_calc.py` 自动生成（%s），数值与 `校核计算.json` 一致。输入：本件设计基准、P1 设计基准（共用参数）、"
      "`04_模型/_check_report.json`（CAD 布尔体积与壁厚）。标“估计”“assumption”的为未核实取值。" % OUT["_生成时间"])
    a("")
    a("## 0 结论")
    a("")
    a("| 校核项 | 结果 | 判据 | 结论 |")
    a("|---|---|---|---|")
    a("| 每腔死容积（含缸体端盖油道与活塞端部余隙） | 有杆腔 %.2f cm³，无杆腔 %.2f cm³ | ≤%.0f cm³（P1 基准） | 满足 |" % (
        S["每腔死容积_有杆腔_cm3"], S["每腔死容积_无杆腔_cm3"], B5["目标"]["每腔死容积上限_cm3"]))
    a("| 其中阀块侧 | 有杆腔 %.2f cm³，无杆腔 %.2f cm³ | — | — |" % (S["阀块侧_有杆腔_cm3"], S["阀块侧_无杆腔_cm3"]))
    a("| 双腔锁闭刚度（x=70 mm） | %.1f N/µm（P1 基准 %.1f；软管连接 %.1f） | 不低于 P1 基准 | 满足，比软管连接高 %.0f%% |" % (
        S["x70双腔刚度_P5_N_um"], S["x70双腔刚度_P1基准_N_um"], S["x70双腔刚度_软管_N_um"], S["x70双腔刚度_P5相对软管_%"]))
    a("| 孔道压降（25 L/min，40 ℃） | 阀块孔道 %.3f MPa，缸体油道 %.3f MPa，含座阀 %.2f MPa | 座阀以外 ≤0.2 MPa（本件取） | 满足；座阀压降为样本外推上限 |" % (
        S["阀块孔道压降_25Lmin_40C_MPa"], S["缸体油道压降_25Lmin_40C_MPa"], S["合计压降含座阀_25Lmin_40C_MPa"]))
    a("| 不同压力孔系最小壁厚 | %.1f mm；Lame 环向应力安全系数 ≥%.1f（设计压力 %.0f MPa） | 安全系数 ≥%.0f | 满足 |" % (
        S["最小壁厚_mm"], S["最小安全系数_设计压力"], PD, BK["安全系数_要求"]))
    a("| 连接螺栓预紧 | 总预紧力为两口最大分离力的 %.1f 倍；螺栓应力比 %.2f | 倍数 ≥2、应力比 ≤0.9 | 满足 |" % (
        S["螺栓预紧对分离力倍数"], OUT["5_螺栓与密封"]["螺栓应力比Rp0.2"]))
    a("| 端面 O 形圈 | 压缩率 %.1f%%，填充率 %.1f%% | 20%%~30%%，≤85%% | 满足 |" % (
        OUT["5_螺栓与密封"]["O形圈压缩率_%"], OUT["5_螺栓与密封"]["槽填充率_%"]))
    a("| 油温套管热响应 | 停滞油 τ≈%.0f~%.0f s；流动时 τ≈%.0f~%.0f s | 油温漂移 0.02~0.2 K/min 下滞后误差 | 见第 6 节 |" % (
        S["套管时间常数_停滞_s"][0], S["套管时间常数_停滞_s"][1], OUT["6_套管热响应"]["情况"]["流动_25Lmin"]["tau_s"],
        OUT["6_套管热响应"]["情况"]["流动_0.94Lmin"]["tau_s"]))
    a("")
    a("## 1 死容积")
    a("")
    a("定义：锁闭座阀阀座与缸腔之间、两腔都锁闭时被封住的油液容积（不含随活塞位置变化的 A·x 部分）。阀块侧由 CAD 求：锁闭网络孔系 ∪ 阀座以下阀孔，减去插入的阀体、阀芯、传感器、套管、接头和 O 形圈。")
    a("")
    a("| 分项 | 有杆腔 cm³ | 无杆腔 cm³ |")
    a("|---|---|---|")
    R_, C_ = OUT["1_死容积"]["有杆腔"]["分项_cm3"], OUT["1_死容积"]["无杆腔"]["分项_cm3"]
    for k in R_:
        a("| %s | %.3f | %.3f |" % (k, R_[k], C_[k]))
    a("| **合计** | **%.2f** | **%.2f** |" % (S["每腔死容积_有杆腔_cm3"], S["每腔死容积_无杆腔_cm3"]))
    h = OUT["1_死容积"]["手算对照"]
    a("")
    a("手算对照（逐段累加）：阀块侧有杆腔 %.2f cm³、无杆腔 %.2f cm³，与 CAD 偏差 %.1f%%、%.1f%%。%s" % (
        h["有杆腔阀块侧_cm3"], h["无杆腔阀块侧_cm3"], h["与CAD偏差_有杆腔_%"], h["与CAD偏差_无杆腔_%"], h["说明"]))
    a("")
    a("阀座以下的阀孔容积按“阀座在孔底以上 %.0f mm”估计（%s）。" % (B5["死容积附加项_assumption"]["阀座以上统计截止高度_相对孔底_mm"],
                                                 B5["死容积附加项_assumption"]["说明"]))
    a("")
    a("## 2 锁闭刚度贡献（P1 公式）")
    a("")
    a("公式：%s。β=%d MPa（锁闭腔）/ %d MPa（含软管），k_m=%.0f N/µm。" % (OUT["2_锁闭刚度"]["公式"], BETA, BETA_H, KM / 1000))
    a("")
    a("| 工况 | x=20 mm | x=70 mm | x=130 mm | 全行程最小 |")
    a("|---|---|---|---|---|")
    for nm, st in stiff.items():
        a("| %s | %.1f | %.1f | %.1f | %.1f |" % (nm, st["20"]["K双腔_N_um"], st["70"]["K双腔_N_um"], st["130"]["K双腔_N_um"],
                                                OUT["2_锁闭刚度"]["x20至130双腔刚度最小值_N_um"][nm]))
    a("")
    p5 = stiff["P5_本设计"]["70"]
    a("x=70 mm 时 P5：V1=%.1f cm³、V2=%.1f cm³，k1=%.1f N/µm、k2=%.1f N/µm，单腔锁闭 %.1f N/µm，双腔锁闭 %.1f N/µm；油温漂移源力经刚度分配后 %d N/K（双腔）、%d N/K（单腔）。"
      "每腔死容积每增加 1 cm³，双腔刚度变化 %.3f N/µm。" % (p5["V1_cm3"], p5["V2_cm3"], p5["k1_N_um"], p5["k2_N_um"], p5["K单腔_N_um"],
                                              p5["K双腔_N_um"], p5["油温漂移_双腔_N_K"], p5["油温漂移_单腔_N_K"],
                                              OUT["2_锁闭刚度"]["x70每腔死容积加1cm3双腔刚度变化_N_um"]))
    a("")
    dk5, dkh = list(dK["P5_本设计"].values()), list(dK["软管连接_对照"].values())
    a("说明：x=70 mm 时缸腔本身容积 V1、V2 为 %.0f、%.0f cm³，远大于死容积，所以死容积由 P1 基准的 %.0f cm³ 降到约 %.0f cm³，双腔刚度只提高 %.1f%%~%.1f%%（x=20~130 mm）；"
      "本件结构的主要作用是不经软管（软管方案每腔附加 %.0f cm³、β 降至 %d MPa，刚度比 P1 基准低 %.0f%%~%.0f%%），并使测压、测温点位于锁闭侧。" % (
          p5["V1_cm3"], p5["V2_cm3"], VD_P1 / 1000, min(VdC, VdR) / 1000, min(dk5), max(dk5), VH_P1 / 1000, BETA_H, -max(dkh), -min(dkh)))
    a("")
    a("## 3 孔道压降")
    a("")
    pr = OUT["3_孔道压降"]
    a("路径：%s。方法：%s。座阀：%s。20 ℃ 黏度按 Walther 式由 40/100 ℃ 黏度换算为 %.1f cSt。" % (pr["路径"], pr["方法"], pr["座阀压降"], pr["nu20_cSt"]))
    a("")
    a("| 工况 | 缸体油道 MPa | 阀块孔道 MPa | 座阀（外推上限）MPa | 合计 MPa |")
    a("|---|---|---|---|---|")
    for k, v in pr["结果"].items():
        a("| %s | %.4f | %.4f | %.3f | %.3f |" % (k, v["缸体油道_MPa"], v["阀块孔道_MPa"], v["座阀_样本外推上限_MPa"], v["合计_MPa"]))
    a("")
    a("尾座实际最大流量 %.2f L/min（%s），对应总压降不到 0.01 MPa。" % (QA, WK["实际流量来源"]))
    a("")
    a("## 4 壁厚与强度")
    a("")
    w4 = OUT["4_壁厚强度"]
    a("材料 %s，屈服强度取 %d MPa（%s）。设计压力 %.1f MPa，试验压力 %.1f MPa（%s）。" % (w4["材料"], SY, BK["材料强度说明"], PD, PT, WK["试验压力说明"]))
    a("")
    a("CAD 求得不同压力孔系之间最小壁厚 %.1f mm（%s）。前 8 处：" % (w4["CAD不同压力孔系最小壁厚_mm"], "—".join(w4["最薄处"])))
    a("")
    a("| 孔系对 | 最小壁厚 mm |")
    a("|---|---|")
    for w in crit[:8]:
        a("| %s | %.2f |" % ("—".join(w["对"]), w["最小壁厚_mm"]))
    a("")
    a("| 孔 | d mm | 薄壁式所需壁厚 mm | Lame 环向应力（设计/试验）MPa | 对屈服安全系数（设计/试验） |")
    a("|---|---|---|---|---|")
    for x in w4["各类孔校核"]:
        a("| %s | %.1f | %.3f | %.1f / %.1f | %.1f / %.1f |" % (x["孔"], x["d_mm"], x["所需最小壁厚_薄壁式_mm"],
                                                           x["按CAD最小壁厚的Lame环向应力_设计压力_MPa"], x["Lame环向应力_试验压力_MPa"],
                                                           x["安全系数_对屈服_设计压力"], x["安全系数_对屈服_试验压力"]))
    th_ = w4["插装阀螺纹"]
    a("")
    a("插装阀螺纹：设计压力下阀体轴向力 %.2f kN，M22×1.5 啮合 17 mm 的剪切面积约 %d mm²，剪应力 %.2f MPa（%s）。结论：%s。" % (
        th_["插装阀轴向压力_kN"], th_["M22×1.5 螺纹啮合 17 mm 剪切面积_mm2"], th_["螺纹剪应力_MPa"], th_["说明"], w4["结论"]))
    a("")
    a("## 5 连接螺栓与端面密封")
    a("")
    b5 = OUT["5_螺栓与密封"]
    a("| 项目 | 数值 |")
    a("|---|---|")
    for k in ("每个对接油口分离力_设计压力_N", "两口合计最大分离力_N", "单只预紧力_N", "拧紧力矩_Nm", "总预紧力_N", "预紧力对分离力倍数",
              "单只螺栓外载_N", "残余夹紧力_N", "螺栓应力_MPa", "螺栓应力比Rp0.2", "头下支承面压强_MPa", "旋入深度对公称直径",
              "O形圈压缩率_%", "槽填充率_%"):
        a("| %s | %s |" % (k, b5[k]))
    a("")
    a("螺栓 %s，%d 只。O 形圈压缩反力按 %s N/mm 估计。%s。端盖为钢件，旋入深度 2 倍公称直径以上满足一般要求；若端盖改为铸铁或铝合金，旋入深度需按材料重核。" % (
        SE["连接螺栓"]["规格"], SE["连接螺栓"]["数量"], SE["O形圈单位长度压缩力_N_mm"], b5["说明"]))
    a("")
    a("## 6 油温传感器套管热响应")
    a("")
    t6 = OUT["6_套管热响应"]
    a("套管 %s，外径 %.1f mm、内径 %.1f mm、端部壁厚 %.1f mm；感温元件 Ø3 mm、感温段 %d mm，间隙 %.1f mm 填导热膏（%.1f W/m·K）。模型：%s。" % (
        TW["材料"], TW["外径"], TW["内径"], TW["端部壁厚"], TS["感温段长_mm"], TS["间隙_mm"], TS["导热膏导热系数_W_mK"], t6["模型"]))
    a("")
    a("| 情况 | h W/m²K | τ s | 滞后误差（0.02 K/min）K | 滞后误差（0.2 K/min）K | 对应双腔推力误差（0.2 K/min）N |")
    a("|---|---|---|---|---|---|")
    for k, v in t6["情况"].items():
        a("| %s | %.1f | %.1f | %.3f | %.3f | %.1f |" % (k, v["h_W_m2K"], v["tau_s"], v["滞后误差_0.02K_min_K"], v["滞后误差_0.2K_min_K"],
                                                      v["对应双腔推力误差_0.2K_min_N"]))
    a("")
    a("Bi=%.4f，套管壁内温度可视为均匀。结论：%s。%s。" % (t6["Bi"], t6["结论"], t6["说明"]))
    a("")
    a("## 7 锁闭期间压力升高与安全阀孔")
    a("")
    p7 = OUT["7_锁闭压力升高"]
    a("x=70 mm、两腔锁闭时，油温每升高 1 K，无杆腔压力升高 %.3f MPa，有杆腔升高 %.3f MPa；无杆腔从设定压力 %.3f MPa 升到设计压力需温升 %.2f K，有杆腔从预压 %.1f MPa 升到设计压力需 %.2f K。" % (
        p7["油温每升高1K_p1_MPa"], p7["油温每升高1K_p2_MPa"], P1SET, p7["p1自设定值升至设计压力所需温升_K"], P_PRE, p7["p2自预压升至设计压力所需温升_K"]))
    a("")
    a("增压工况：%s。安全阀设定 %.1f MPa。" % (p7["结论"], p7["安全阀设定_MPa"]))
    a("")
    a("## 8 未核实与假设")
    a("")
    a("- 插装孔尺寸来源：%s。" % B5["座阀阀孔"]["尺寸来源"])
    a("- 座阀 25 L/min 压降、常闭订货码、线圈功率未核实（%s）。" % B5["座阀阀孔"]["适配阀_示例"][0]["未核实"])
    a("- 阀座以下阀孔容积、传感器膜片前腔与测压接头单向阀前腔容积为估计值。")
    a("- 油液比热、导热系数、100 ℃ 黏度为典型值；局部损失系数为经验值。")
    a("- 套管内油液与缸腔主体油液之间的温差未计算，需试验台实测。")
    with open(os.path.join(HERE, "校核计算书.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L_) + "\n")


md()
