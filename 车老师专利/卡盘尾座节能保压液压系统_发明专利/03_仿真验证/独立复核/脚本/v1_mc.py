# -*- coding: utf-8 -*-
"""V1-10 蒙特卡洛复核（独立模型 v1_qs，确定性测量，N=600，种子与 C 不同）。
随机范围与 C 的 sim_all.py st_mc 相同：β 800~1600（软管 β 同比例）、F_s 50~300 N、k_m 50~200 N/µm、空气 0~1%、
内泄漏 0.1~4（对数均匀）、伸出量 20~130 mm、伸长 20~140 µm、τ 3~15 min、油温速率 ±0.2 K/min。
C 计入传感器偏差与噪声，V1 不计；两者 P95 的差别即包含这一项。"""
import math, os
import numpy as np
from v1_qs import simulate, growth
from v1_common import dump, MPa, um

N = int(os.environ.get("V1_MC_N", "600"))
rng = np.random.default_rng(20261002)
rows = []
for i in range(N):
    b = rng.uniform(800, 1600) * MPa
    ov = dict(beta0=b, beta_hose=b * 800 / 1200, Fs=rng.uniform(50, 300), km=rng.uniform(50, 200) / um,
              air=rng.uniform(0, 0.01), x=rng.uniform(0.02, 0.13))
    lm = 10 ** rng.uniform(-1, math.log10(4))
    dL, tau, dT = rng.uniform(20, 140), rng.uniform(180, 900), rng.uniform(-0.2, 0.2) / 60
    row = {}
    for s in ("M1s", "M2"):
        r = simulate(s, delta=growth(dL, tau), dTdt=dT, leak_mult=lm, dt=1.0, **ov)
        row[s] = {"dev%": max(r["max_pos%"], -r["max_neg%"]), "pos%": r["max_pos%"], "n": r["n_act"]}
    rows.append(row)
S = {}
for s in ("M1s", "M2"):
    dev = np.array([r[s]["dev%"] for r in rows]); pos = np.array([r[s]["pos%"] for r in rows])
    n = np.array([r[s]["n"] for r in rows])
    S[s] = {"N": N, "偏差均值%": float(dev.mean()), "P95%": float(np.percentile(dev, 95)), "最大%": float(dev.max()),
            "偏差>10%比例": float(np.mean(dev > 10)), "超安全上限25%比例": float(np.mean(pos > 25)),
            "动作次数均值": float(n.mean()), "动作次数P95": float(np.percentile(n, 95))}
    print(s, S[s])
dump("v1_mc", {"汇总": S})
