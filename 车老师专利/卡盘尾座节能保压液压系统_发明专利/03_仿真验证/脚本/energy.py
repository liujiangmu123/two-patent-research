# -*- coding: utf-8 -*-
"""能耗模型（单件循环与保压阶段）。
M0 ：定量泵 14.5 L/min 连续运转，全部多余流量经 5 MPa 溢流阀回油（课题组 AMESim 基线）。
其余方案：4 cc/rev 泵 + 1 L 蓄能器，蓄能器压力降到 pmin 时泵起动充液到 pmax 后停机。
  保压阶段蓄能器的耗油 = 与蓄能器连通元件的泄漏 + 控制动作取油（由 tail_qs 给出）。
  - 现有技术（M1b、M1c）：蓄能器经换向阀 11/18（滑阀）和减压阀 10/16/17 常通，存在滑阀与减压阀泄油；
    卡盘夹紧腔经回转接头持续供压，回转接头泄漏由蓄能器承担。
  - 本发明（M2）：隔离座阀 V0 关闭，滑阀与减压阀与蓄能器隔开；卡盘由内置液控单向阀锁闭、换向阀回中位，
    回转接头不带压；每 t_rep 秒复压确认一次（复压补油 = 夹紧腔泄漏量 + 回转接头在复压时长内的泄漏）。
泵轴功率 = p·Q_th/η_hm（η_hm=η_t/η_v）；电功率 = 轴功率/η_motor + 运行时空载损耗中的电机部分（假设已含在 η_motor）。
"""
import numpy as np
import hydro as H
from params import MPa, cm3, Lmin


def p_hold_M0(P):
    """M0 保压阶段泵轴功率与溢流损失（W）。泵全部流量在溢流压力下排出，负载流量≈0。"""
    eta_hm = 0.97                     # assumption：CBF-E10 机械效率，用于对照 AMESim 1.24 kW
    p = P["M0_p_crack"] + P["M0_Q"] / P["M0_grad"]      # 溢流阀全流量压力（含调压偏差）
    Qr = P["M0_Q"] * 0.99             # 回转接头等泄漏约 0.1~0.2 L/min，其余全部溢流
    Pin = p * P["M0_Q"] / eta_hm
    Pr = p * Qr
    return {"泵轴功率W": Pin, "溢流损失W": Pr, "溢流阀压力MPa": p / MPa, "溢流占比%": 100 * Pr / Pin}


def leak_rate(P, s):
    """保压阶段蓄能器侧泄漏（m3/s），按平均蓄能器压力计算。"""
    pa = 0.5 * (P["pmin_acc"] + P["pmax_acc"])
    rot = P["C_rot"] * P["p_chuck"]                       # 回转接头泄漏（夹紧压力下）
    spool = P["n_spool"] * P["C_spool"] * pa
    red = P["n_red"] * P["C_red"] * pa
    seat = 4 * 1e-4 * cm3 / 60 / MPa * pa
    if s in ("M1b", "M1c", "M1", "M1s"):
        return {"滑阀": spool, "减压阀泄油": red, "回转接头": rot, "座阀": 0.0}
    # 本发明：V0 隔离，只剩 V0 与锁闭座阀的座阀泄漏
    return {"滑阀": 0.0, "减压阀泄油": 0.0, "回转接头": 0.0, "座阀": seat}


def charge_energy(P, V):
    """蓄能器充液 V（m3）所需泵轴能量（J）与时长（s）；充液按绝热，平均压力取 pmin~pmax 均值。"""
    Qe = P["Q_th"] * P["eta_v"]
    t = V / Qe
    pa = 0.5 * (P["pmin_acc"] + P["pmax_acc"])
    eta_hm = P["eta_t"] / P["eta_v"]
    return pa * P["Q_th"] / eta_hm * t, t


def hold_energy(P, s, t_hold, V_ctrl=0.0, t_rep=60.0, t_rep_on=1.0):
    """保压阶段 t_hold 内能耗。V_ctrl：控制动作从蓄能器取油（m3）。"""
    if s == "M0":
        r = p_hold_M0(P)
        E = r["泵轴功率W"] * t_hold
        return {"轴能量kJ": E / 1e3, "平均轴功率W": r["泵轴功率W"], "电能kJ": E / P["eta_motor"] / 1e3,
                "起动次数": 0, "泄漏cm3": float("nan"), "明细": r}
    lk = leak_rate(P, s)
    V = sum(lk.values()) * t_hold + V_ctrl
    if s in ("M2", "M2b", "M2S", "M2h"):
        n_rep = int(t_hold // t_rep)
        V_chk = P["C_chk"] * P["p_chuck"] * t_hold + n_rep * P["C_rot"] * P["p_chuck"] * t_rep_on
        V += V_chk
        lk["卡盘复压"] = V_chk / t_hold
    Vu = H.acc_usable(P, n=1.0)                                  # 放液慢，等温
    n_start = V / Vu
    Ech, tch = charge_energy(P, V)
    E = Ech + n_start * P["E_start"]
    Eel = Ech / P["eta_motor"] + n_start * P["E_start"]
    return {"轴能量kJ": E / 1e3, "平均轴功率W": E / t_hold, "电能kJ": Eel / 1e3,
            "起动次数": n_start, "泵运行时长s": tch, "耗油cm3": V / cm3,
            "泄漏分项cm3_min": {k: v / cm3 * 60 for k, v in lk.items()}, "蓄能器可用容积cm3": Vu / cm3}


def cycle_energy(P, s, V_ctrl=0.0):
    """单件循环（夹紧 1.2 s → 前进 14 s → 保压 600 s → 后退 10 s → 松开 0.6 s → 装卸 30 s）能耗。
    动作阶段（26 s，假设）：M0 泵照常溢流；其余方案泵运行，平均在蓄能器均压下供油（偏保守）。
    装卸 30 s：M0 泵继续溢流；其余方案按保压阶段漏油处理。"""
    c = P["cycle"]
    t_move = c["夹紧"] + c["尾座前进"] + c["尾座后退"] + c["松开"]
    if s == "M0":
        Pw = p_hold_M0(P)["泵轴功率W"]
        E = Pw * sum(c.values())
        return {"单件轴能量kJ": E / 1e3, "单件电能kWh": E / P["eta_motor"] / 3.6e6}
    eta_hm = P["eta_t"] / P["eta_v"]
    pa = 0.5 * (P["pmin_acc"] + P["pmax_acc"])
    Em = pa * P["Q_th"] / eta_hm * t_move + P["E_start"]
    h = hold_energy(P, s, c["保压加工"] + c["装卸"], V_ctrl)
    E = Em + h["轴能量kJ"] * 1e3
    Eel = Em / P["eta_motor"] + h["电能kJ"] * 1e3
    return {"单件轴能量kJ": E / 1e3, "单件电能kWh": Eel / 3.6e6}


def annual(P, cyc):
    tcyc = sum(P["cycle"].values())
    n = P["shift_h"] * 3600 / tcyc * P["shifts_y"]
    kwh = cyc["单件电能kWh"] * n
    return {"年件数": n, "年电能kWh": kwh, "年电费元": kwh * P["price"]}
