# -*- coding: utf-8 -*-
"""V1-4 能耗独立复算（M0 原系统、M1 小泵卸荷、M2/M1b 现有间歇保压、M3/本发明）。
与 C 的区别：蓄能器充液能量按多变过程 ∫p dV 积分（不是平均压力×体积），泵起动次数取整（ceil），
并给出 1.24 kW 解释为“泵轴输入”与“电机输入”两种口径，以及电磁阀线圈、复压周期等敏感性。
名称对照：C 的 M1s/M1b ≈ B 的 M2（现有间歇保压）；C 的 M2 = B 的 M3（本发明）。
"""
import math
from v1_common import BASE, dump

B = BASE
pu, ac, ch = B["动力源"], B["蓄能器8"], B["卡盘液压缸12"]
PATM = 0.101325
Qth = pu["理论流量_L_min"]            # L/min
eta_v, eta_t, eta_m = pu["容积效率"], pu["总效率"], 0.80
V0 = ac["容积_L"] * 1000             # cm3
p0, pmin, pmax = ac["充气压力_p0_20C"], ac["最低工作压力_pmin"], ac["最高工作压力_pmax"]
cyc = {"夹紧": 1.2, "前进": 14.0, "保压": 600.0, "后退": 10.0, "松开": 0.6, "装卸": 30.0}
Tc = sum(cyc.values())
t_move = cyc["夹紧"] + cyc["前进"] + cyc["后退"] + cyc["松开"]
t_hold = cyc["保压"] + cyc["装卸"]
N_year = 8 * 3600 / Tc * 250


def gasV(p, n):
    return V0 * ((p0 + PATM) / (p + PATM)) ** (1 / n)


def usable(n):
    return gasV(pmin, n) - gasV(pmax, n)


def charge_work_J(n=1.4, steps=400):
    """充液 pmin→pmax 的液压功 ∫p dV（J），绝热。"""
    W = 0.0
    for i in range(steps):
        pa = pmin + (pmax - pmin) * i / steps
        pb = pmin + (pmax - pmin) * (i + 1) / steps
        dV = gasV(pa, n) - gasV(pb, n)
        W += 0.5 * (pa + pb) * dV       # MPa·cm3 = J
    return W


def elec_per_charge(n_start_extra_s=0.5):
    """一次完整充液的电能 J：液压功 / (η_t·η_m)，加起动附加（额定 0.75 kW × 0.5 s）。"""
    return charge_work_J() / (eta_t * eta_m) + pu["电机_kW"] * 1e3 * n_start_extra_s


import os
FIX = os.environ.get("V1_ENERGY_FIX", "1") == "1"     # v1.1 修正口径（见报告第 3 节）：①动作段泵轴功率按有效流量 Q_th·η_v 计（v1.0 按理论流量÷总效率，
               # 重复计入容积损失，偏高 1/η_v）；②充液功与起动次数同取等温可用容积（v1.0 充液功按绝热可用容积 111.5 cm3、
               # 起动次数按等温 147.8 cm3，每 cm3 充液功低于 p_min，物理上偏低）。FIX=False 复现 v1.0。


def model(q_hold_cm3_min, coil_W=0.0, start_ceil=True):
    """非 M0 方案单件电能（Wh）。动作段：泵在蓄能器均压下运转 t_move（与 B、C 相同的保守口径）。"""
    p_acc = 0.5 * (pmin + pmax)
    E_move = p_acc * Qth / 60 * 1e3 * (eta_v if FIX else 1.0) / (eta_t * eta_m) * t_move    # W·s
    V = q_hold_cm3_min * t_hold / 60
    Vu = usable(1.0)                     # 慢放液等温
    n = V / Vu
    n_eff = math.ceil(n) if start_ceil and n > 0 else n
    E_hold = n * charge_work_J(n=1.0 if FIX else 1.4) / (eta_t * eta_m) + n_eff * pu["电机_kW"] * 1e3 * 0.5
    E = E_move + E_hold + coil_W * t_hold
    return {"单件Wh": E / 3600, "保压Wh": (E_hold + coil_W * t_hold) / 3600, "保压平均电功率W": (E_hold + coil_W * t_hold) / t_hold,
            "保压耗油cm3": V, "起动次数": n, "年kWh": E / 3600 * N_year / 1e3}


R = {"蓄能器可用_等温cm3": usable(1.0), "蓄能器可用_绝热cm3": usable(1.4), "单次充液液压功J": charge_work_J(),
     "年件数": N_year}

# M0：14.5 L/min @ 5.0725 MPa（C 取溢流阀调压偏差），两种口径
P_hyd = 14.5 / 60 * 5.0725 * 1e3      # W
R["M0"] = {
    "液压功率W": P_hyd,
    "口径A_1.24kW为泵轴输入(÷η_m)_单件Wh": 1240 / eta_m * Tc / 3600,
    "口径B_1.24kW为电机输入_单件Wh": 1240 * Tc / 3600,
    "按物理_液压功率/η_hm0.97/η_m_单件Wh": P_hyd / 0.97 / eta_m * Tc / 3600,
}

# 现有间歇保压（C:M1s/M1b，B:M2）：滑阀 2×5、减压阀 3×c_red（C=1，B=2 cm3/min/MPa）@5.5 MPa，回转接头 0.7 L/min@3MPa 线性→2 MPa
rj = ch["回转接头泄漏_L_min_at_3MPa"] * 1000 / 3 * ch["夹紧压力_额定"]
for lab, cred in (("c_red=1(C)", 1.0), ("c_red=2(B)", 2.0)):
    q = 2 * 5 * 5.5 + 3 * cred * 5.5 + rj
    R["现有间歇保压_" + lab] = dict(model(q), 泄漏cm3_min=q)
# 回转接头按孔口（√Δp）而非线性
q_orf = 2 * 5 * 5.5 + 3 * 1 * 5.5 + 700 * math.sqrt(2 / 3)
R["现有间歇保压_回转接头孔口律"] = dict(model(q_orf), 泄漏cm3_min=q_orf)

# 本发明：V0 隔离；卡盘每 T 复压一次，带压 t_on，期间回转接头 + 滑阀 + 减压阀漏；尾座回复取油
def invention(T_rep=60.0, t_on=1.0, tail_events=6, tail_cm3=0.3, coil_W=0.0, seat=1e-4):
    q_seat = 4 * seat * 5.5
    q_rep = (rj + 5 * 5.5 + 1 * 5.5) * t_on / T_rep
    q_tail = tail_events * tail_cm3 / (t_hold / 60)
    q = q_seat + q_rep + q_tail
    return dict(model(q, coil_W), 泄漏cm3_min=q, 分项={"座阀": q_seat, "卡盘复压": q_rep, "尾座回复": q_tail})

R["本发明_基准(60s,1s)"] = invention()
R["本发明_B口径(60s,0.5s)"] = invention(t_on=0.5)
R["本发明_复压30s(C修订建议)"] = invention(T_rep=30)
R["本发明_复压30s+带压2s"] = invention(T_rep=30, t_on=2.0)
R["本发明_尾座回复50次/循环"] = invention(tail_events=50)
R["本发明_座阀泄漏0.1cm3/min/MPa"] = invention(seat=0.1)
R["本发明_V0常开需线圈保持15W"] = invention(coil_W=15.0)

base = R["M0"]["口径A_1.24kW为泵轴输入(÷η_m)_单件Wh"]
for k, v in list(R.items()):
    if isinstance(v, dict) and "单件Wh" in v:
        v["相对M0节电%(口径A)"] = 100 * (1 - v["单件Wh"] / base)
        v["相对M0节电%(口径B)"] = 100 * (1 - v["单件Wh"] / R["M0"]["口径B_1.24kW为电机输入_单件Wh"])
R["口径"] = "v1.1 修正（动作段按有效流量；充液功按等温可用容积）" if FIX else "v1.0 原口径"
R["单次充液液压功_等温J"] = charge_work_J(n=1.0)
dump("v1_energy" if FIX else "v1_energy_v10", R)
for k, v in R.items():
    print(k, v)
