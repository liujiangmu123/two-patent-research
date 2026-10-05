# -*- coding: utf-8 -*-
"""评价指标：节点 RMSE、分类别 NGED、肢宽/规格/朝向/偏心误差、存在 AUC、置信度校准、有限元响应误差。"""
from __future__ import annotations

import numpy as np

from . import _paths  # noqa: F401
from towerkit import fem as F
from towerkit import loads as LD
from towerkit import sections as TS
from towerkit.graph import TrussGraph, evaluate

from .surfels import frames, sigmoid


def auc(score, label):
    score = np.asarray(score, float); label = np.asarray(label, bool)
    pos, neg = score[label], score[~label]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    ranks = np.argsort(np.argsort(allv)) + 1.0
    # 同分平均秩
    order = np.argsort(allv)
    sv = allv[order]
    r = np.empty_like(ranks)
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def opening_dir(V, mi, mj, r, phi):
    """角钢开口方向（两肢角平分线）单位向量。"""
    u, n1, n2, L = (np.asarray(a) for a in frames(np.asarray(V)[mi], np.asarray(V)[mj], r, np.asarray(phi)))
    w = n1 + n2
    return w / np.linalg.norm(w, axis=1, keepdims=True), n1, n2


def section_name_for_width(b, prefer_t=None):
    """肢宽 → 规格名（肢厚影像不可观测，取该肢宽档的中间厚度；给定 prefer_t 时取最接近者）。"""
    bmm = int(round(b * 1000))
    names = sorted([k for k, a in TS.ANGLES.items() if int(round(a.b * 1000)) == bmm], key=lambda k: TS.ANGLES[k].t)
    if not names:
        k = min(TS.ANGLES, key=lambda k: abs(TS.ANGLES[k].b - b))
        return k
    if prefer_t is not None:
        return min(names, key=lambda k: abs(TS.ANGLES[k].t - prefer_t))
    return names[len(names) // 2]


def build_graph(U, V, present, secs):
    g = TrussGraph()
    for p in V:
        g.add_node(p)
    for e in np.flatnonzero(present):
        g.add_member(U.mi[e], U.mj[e], U.cat[e], U.part[e], secs[e], "Q355", str(e))
    g.meta = {"base_nodes": list(U.g_design.meta["base_nodes"]), "attach": U.g_design.meta.get("attach", [])}
    return g.drop_orphans() if hasattr(g, "drop_orphans") else g


def fe_response(g: TrussGraph, w0=700.0):
    """设计风荷载（w0=0.70 kPa 等效，含导线挂点横向荷载）下塔顶最大水平位移与前 3 阶频率。"""
    m = F.FEModel(g, mass_factor=1.15)
    m.fix_base()
    Fw = LD.wind_static(m, w0=w0, direction=(0.0, 1.0, 0.0)) + LD.conductor_loads(m, vertical=20e3, transverse=6e3)
    u = m.solve_static(Fw)
    U = u.reshape(-1, 6)[:, :3]
    top = np.argmax(g.nodes[:, 2])
    zt = g.nodes[:, 2].max()
    tops = np.flatnonzero(g.nodes[:, 2] > zt - 0.5)
    disp = float(np.max(np.linalg.norm(U[tops, :2], axis=1)))
    try:
        freq, _ = m.modes(3)
        freq = [float(f) for f in freq]
    except Exception:
        freq = [float("nan")] * 3
    return {"tip_disp_m": disp, "freq_Hz": freq, "mass_t": float(m.total_mass() / 1000)}


def evaluate_run(U, x_parts, truth_secs, present_est, b_est, name=""):
    """x_parts: dict(V, b, phi, d1, d2, logit)。返回指标字典。"""
    V = np.asarray(x_parts["V"])
    ex = U.exist
    # 节点（仅统计真值存在杆件所连节点）
    used = np.zeros(len(V), bool)
    used[U.mi[ex]] = True; used[U.mj[ex]] = True
    err = np.linalg.norm(V - U.nodes_true, axis=1)
    out = {"name": name, "RMSEn_m": float(np.sqrt(np.mean(err[used] ** 2))),
           "node_err_p95_m": float(np.percentile(err[used], 95))}
    for c in ("main", "diagonal", "auxiliary"):
        sel = np.zeros(len(V), bool)
        es = np.flatnonzero(ex & (np.array(U.cat) == c))
        sel[U.mi[es]] = True; sel[U.mj[es]] = True
        out[f"RMSEn_{c}_m"] = float(np.sqrt(np.mean(err[sel] ** 2)))
    both = ex & present_est
    out["width_MAE_mm"] = float(1000 * np.mean(np.abs(b_est[both] - U.b[both])))
    for c in ("main", "diagonal", "auxiliary"):
        sel = both & (np.array(U.cat) == c)
        out[f"width_MAE_{c}_mm"] = float(1000 * np.mean(np.abs(b_est[sel] - U.b[sel])))
    out["width_class_acc"] = float(np.mean(np.abs(b_est[both] - U.b[both]) < 1e-4))
    out["width_class_acc_pm1"] = float(np.mean(_within_one_class(b_est[both], U.b[both])))
    # 朝向
    if "phi" in x_parts:
        oe, n1e, n2e = opening_dir(V, U.mi, U.mj, U.r, x_parts["phi"])
        ot, n1t, n2t = opening_dir(U.nodes_true, U.mi, U.mj, U.r, U.phi)
        ang = np.degrees(np.arccos(np.clip(np.sum(oe * ot, 1), -1, 1)))
        out["orient_err_deg_median"] = float(np.median(ang[both]))
        out["orient_err_deg_mean"] = float(np.mean(ang[both]))
        out["orient_correct_rate"] = float(np.mean(ang[both] < 20.0))
        dt = U.d1[:, None] * n1t + U.d2[:, None] * n2t
        de = np.asarray(x_parts["d1"])[:, None] * n1e + np.asarray(x_parts["d2"])[:, None] * n2e
        out["delta_err_mm"] = float(1000 * np.mean(np.linalg.norm(de - dt, axis=1)[both]))
    # 拓扑
    out["exist_AUC"] = auc(np.asarray(sigmoid(np.asarray(x_parts["logit"]))), ex)
    out["exist_acc"] = float(np.mean(present_est == ex))
    out["damaged_removed"] = int(np.sum(~present_est[U.damaged]))
    out["damaged_total"] = int(len(U.damaged))
    out["falseneg_recovered"] = int(np.sum(present_est[U.false_neg]))
    out["falseneg_total"] = int(len(U.false_neg))
    sp = np.flatnonzero(U.is_cand & ~np.isin(np.arange(U.n_members), U.false_neg))
    out["spurious_rejected"] = int(np.sum(~present_est[sp]))
    out["spurious_total"] = int(len(sp))
    # NGED（PTM 口径）
    secs = [section_name_for_width(b) for b in b_est]
    gt = build_graph(U, U.nodes_true, ex, U.sec)
    rec = build_graph(U, V, present_est, secs)
    ev = evaluate(gt, rec, thr=0.5)
    for k in ("NGED_main", "NGED_diagonal", "NGED_auxiliary", "NGED_all"):
        out[k] = float(ev.get(k, float("nan")))
    return out


def _within_one_class(b_est, b_true):
    from .optimize import B_TABLE
    ie = np.argmin(np.abs(b_est[:, None] - B_TABLE[None]), 1)
    it = np.argmin(np.abs(b_true[:, None] - B_TABLE[None]), 1)
    return np.abs(ie - it) <= 1
