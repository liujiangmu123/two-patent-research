# -*- coding: utf-8 -*-
"""V1-6 减压阀回差（不灵敏区）与推力带宽的匹配（第1轮审查意见 G1）。
用 v1_qs 的独立准静态模型：由上方回复时 R1 只溢流到 p1set+Δp_db（回差），由下方回复时补到 p1set；
可选“设定值下移 Δp_db/2”（回复窗口对称于 p1set）。工况 C6（伸长 57.5 µm + 油温 +0.1 K/min + 内泄漏×1）与 C3。
输出：最大正/负偏差、600 s 内动作次数；判据 Δp_db·A1 与 δF0 的比值。"""
import math
from v1_qs import simulate, growth
from v1_common import params, dump, MPa

R = {"说明": "db=减压阀回差 MPa；shift=设定值下移量；ratio=Δp_db·A1/(δF0)"}
P = params()
A1 = P["A1"]
rows = []
for F0 in (2000.0, 6000.0):
    for band in (0.02, 0.05):
        for db in (0.0, 0.05, 0.1, 0.2, 0.3):
            for centered in (False, True):
                if db == 0.0 and centered:
                    continue
                kw = dict(air=0.005, F0=F0, band=band, db_bias=db * MPa, shift=(db * MPa / 2 if centered else 0.0))
                r6 = simulate("M2", delta=growth(57.5, 300), dTdt=0.1 / 60, **kw)
                r3 = simulate("M2", dTdt=0.2 / 60, leak_mult=0.0, **kw)
                row = {"F0_N": F0, "δ": band, "db_MPa": db, "设定下移db/2": centered,
                       "ratio": db * MPa * A1 / (band * F0) if db else 0.0,
                       "C6_max_pos%": r6["max_pos%"], "C6_max_neg%": r6["max_neg%"], "C6_n": r6["n_act"],
                       "C3_max_pos%": r3["max_pos%"], "C3_max_neg%": r3["max_neg%"], "C3_n": r3["n_act"]}
                rows.append(row)
                print(row)
R["扫描"] = rows
dump("v1_db", R)
