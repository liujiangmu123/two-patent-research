# -*- coding: utf-8 -*-
"""评价指标。"""
from __future__ import annotations

import numpy as np

from ._tk import fem
from .confidence import reconstructed_graph
from .sensitivity import design_load, tip_selector

C_LOW = 0.5


def fe_response(g, n_modes=3):
    m = fem.FEModel(g).fix_base()
    u = m.solve_static(design_load(m))
    tip = float(tip_selector(m) @ u)
    f, _ = m.modes(n_modes)
    return tip, f


def metrics(sc, res, fe_gt=None, w=None):
    ex = sc.gt_member_exists
    c = res.c
    nm = len(c)
    # 杆件覆盖：存在杆件 c≥0.5；缺失杆件被正确判为缺失
    correct_missing = (~ex) & (res.exist == -1)
    covered = (ex & (c >= C_LOW)) | correct_missing
    low = c < C_LOW
    dX = res.nodes - sc.gt.nodes
    rmse = float(np.sqrt(np.mean(np.sum(dX ** 2, 1))))
    obs = res.node_est > 0
    rmse_obs = float(np.sqrt(np.mean(np.sum(dX[obs] ** 2, 1)))) if obs.any() else float("nan")
    g = reconstructed_graph(sc.prior, res)
    tip, f = fe_response(g)
    tip_gt, f_gt = fe_gt if fe_gt is not None else fe_response(sc.gt)
    out = {
        "coverage": float(covered.mean()),
        "n_low": int(low.sum()),
        "n_low_main": int((low & (np.asarray(sc.prior.cat) == "main")).sum()),
        "node_rmse": rmse, "node_rmse_observed": rmse_obs, "nodes_direct": int((res.node_est == 2).sum()),
        "nodes_borrowed": int((res.node_est == 1).sum()),
        "missing_detected": int(correct_missing.sum()), "missing_total": int((~ex).sum()),
        "false_missing": int((ex & (res.exist == -1)).sum()),
        "tip_err_pct": float(abs(tip - tip_gt) / abs(tip_gt) * 100),
        "f_err_pct": [float(abs(a - b) / b * 100) for a, b in zip(f, f_gt)],
        "sym_counts": {"一致": int((res.sym_state == 1).sum()), "冲突": int((res.sym_state == -1).sum()),
                       "不可判": int((res.sym_state == 0).sum())},
    }
    if w is not None:
        out["weighted_deficit"] = float(np.sum(w * (1 - c)) / np.sum(w))
    return out
