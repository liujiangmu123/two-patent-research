# -*- coding: utf-8 -*-
"""专利A 主实验补充分析（不重跑反演，读取 _figdata_main.pkl 与 main.json）：
  ① 朝向：按“可翻转杆件”（肢宽 ≥63 mm 且长度 ≥2.5 m）与其余杆件分组，统计初值/结果正确率与纠正数；
  ② 有限元：同一重建几何下，肢厚取“中间厚度规则”与“真值肢厚（oracle）”的对比，量化肢厚不可观测对频率的影响；
  ③ 复测：误报节点与真实位移节点的拓扑距离。
输出 ../数据/analysis_main.json。"""
import json
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "数据")
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from anglegs import metrics as ME  # noqa: E402
from anglegs.hypothesis import FLIP_MIN_B, FLIP_MIN_L  # noqa: E402
from towerkit import sections as TS  # noqa: E402

fd = pickle.load(open(os.path.join(DATA, "_figdata_main.pkl"), "rb"))
M = json.load(open(os.path.join(DATA, "main.json"), encoding="utf-8"))
U = fd["U"]
P = fd["P"]
mi, mj = np.asarray(U["mi"]), np.asarray(U["mj"])
X = np.asarray(U["nodes_true"])
ex = np.asarray(U["exist"])
present = np.asarray(fd["present"])
both = ex & present
L = np.linalg.norm(X[mj] - X[mi], axis=1)
b_true = np.asarray(U["b"])


def orient_ok(V, phi):
    oe, _, _ = ME.opening_dir(V, mi, mj, np.asarray(U["r"]), phi)
    ot, _, _ = ME.opening_dir(X, mi, mj, np.asarray(U["r"]), np.asarray(U["phi"]))
    return np.degrees(np.arccos(np.clip(np.sum(oe * ot, 1), -1, 1))) < 20.0


ok0 = orient_ok(np.asarray(fd["V_noisy"]), np.asarray(fd["init_phi"]))
ok1 = orient_ok(np.asarray(P["V"]), np.asarray(P["phi"]))
elig = both & (b_true >= FLIP_MIN_B) & (L >= FLIP_MIN_L)
rest = both & ~elig
out = {"orientation": {
    "flip_rule": {"FLIP_MIN_B_m": FLIP_MIN_B, "FLIP_MIN_L_m": FLIP_MIN_L},
    "eligible_n": int(elig.sum()), "eligible_init_correct": float(ok0[elig].mean()),
    "eligible_final_correct": float(ok1[elig].mean()),
    "eligible_init_wrong": int((~ok0 & elig).sum()), "eligible_fixed": int((~ok0 & ok1 & elig).sum()),
    "eligible_broken": int((ok0 & ~ok1 & elig).sum()),
    "rest_n": int(rest.sum()), "rest_init_correct": float(ok0[rest].mean()), "rest_final_correct": float(ok1[rest].mean()),
    "rest_fixed": int((~ok0 & ok1 & rest).sum()), "rest_broken": int((ok0 & ~ok1 & rest).sum()),
    "all_init_correct": float(ok0[both].mean()), "all_final_correct": float(ok1[both].mean())}}
for c in ("main", "diagonal", "auxiliary"):
    s = both & (np.asarray(U["cat"]) == c)
    out["orientation"][f"{c}_init_correct"] = float(ok0[s].mean())
    out["orientation"][f"{c}_final_correct"] = float(ok1[s].mean())


# ② 肢厚影响：真值肢厚（oracle）下的有限元响应
class _U:
    pass


Uo = _U()
for k, v in U.items():
    setattr(Uo, k, v)
from anglegs import synth as SY  # noqa: E402
from towerkit.graph import TrussGraph  # noqa: E402


def build(V, pres, secs):
    g = TrussGraph()
    for p in V:
        g.add_node(p)
    for e in np.flatnonzero(pres):
        g.add_member(int(mi[e]), int(mj[e]), U["cat"][e], U["part"][e], secs[e], "Q355", str(e))
    meta = M["scene"]
    return g


b_snap = np.asarray(fd["b_snap"])
t_true = np.array([TS.angle(s).t if s else 0.005 for s in U["sec"]])
secs_mid = [ME.section_name_for_width(b) for b in b_snap]
secs_orc = [ME.section_name_for_width(b, prefer_t=t) for b, t in zip(b_snap, t_true)]
Uf = SY.build_universe("suspension", seed=int(M["scene"]["seed"]))
assert np.allclose(Uf.nodes_true, X)
fe_true = ME.fe_response(ME.build_graph(Uf, Uf.nodes_true, Uf.exist, Uf.sec))
fe_mid = ME.fe_response(ME.build_graph(Uf, np.asarray(P["V"]), present, secs_mid))
fe_orc = ME.fe_response(ME.build_graph(Uf, np.asarray(P["V"]), present, secs_orc))


def rel(v):
    return {"tip_err_rel": abs(v["tip_disp_m"] - fe_true["tip_disp_m"]) / fe_true["tip_disp_m"],
            "freq_err_rel_max": float(np.max(np.abs(np.array(v["freq_Hz"]) - np.array(fe_true["freq_Hz"]))
                                             / np.array(fe_true["freq_Hz"]))),
            "mass_err_rel": (v["mass_t"] - fe_true["mass_t"]) / fe_true["mass_t"], **v}


out["thickness"] = {"note": "同一重建几何与肢宽，肢厚分别取该肢宽档中间厚度（本发明默认，影像不可观测）与真值肢厚（oracle）",
                    "secs_mid_eq_true_rate": float(np.mean([a == b for a, b, e in zip(secs_mid, U["sec"], both) if e])),
                    "secs_orc_eq_true_rate": float(np.mean([a == b for a, b, e in zip(secs_orc, U["sec"], both) if e])),
                    "fe_true": fe_true, "fe_mid_thickness": rel(fe_mid), "fe_oracle_thickness": rel(fe_orc)}
# ③ 复测误报节点与位移节点的拓扑距离
ch = M["多期变化检测"]
adj = {}
for a, b in zip(mi[ex], mj[ex]):
    adj.setdefault(int(a), set()).add(int(b)); adj.setdefault(int(b), set()).add(int(a))


def hop(s, t):
    seen, fr, d = {s}, [s], 0
    while fr:
        if t in fr:
            return d
        d += 1
        nxt = []
        for u in fr:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v); nxt.append(v)
        fr = nxt
    return -1


out["change"] = {"moved_node": ch["moved_node"], "flagged": ch["flagged_nodes"],
                 "hops_from_moved": {str(k): hop(ch["moved_node"], k) for k in ch["flagged_nodes"]}}
json.dump(out, open(os.path.join(DATA, "analysis_main.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
