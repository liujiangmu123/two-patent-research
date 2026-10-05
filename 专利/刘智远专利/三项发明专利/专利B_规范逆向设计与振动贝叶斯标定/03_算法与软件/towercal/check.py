# -*- coding: utf-8 -*-
"""标定模型的设计风荷载响应与规范验算，以及评价指标。"""
from __future__ import annotations

import numpy as np

from .design import Scenario, load_cases, stress_ratios
from .model import ORDER


def top_node(pt):
    X = pt.X
    cand = [i for i, t in enumerate(pt.g.ntype) if t == "corner"]
    return max(cand, key=lambda i: X[i, 2])


def design_response(pt, di, sc: Scenario, sections, theta=(1.0, 11.0)):
    """设计风荷载（标准组合、大风 90°）塔顶水平位移 m；基本组合各杆应力比包络。"""
    fem = pt.as_femodel(sections, theta)
    cases_k = load_cases(fem, di, sc, factored=False)
    cases_d = load_cases(fem, di, sc, factored=True)
    U = pt.solve_static(np.array([cases_k[0][1]] + [c[1] for c in cases_d]), sections, theta)
    tn = top_node(pt)
    disp = float(np.hypot(U[0, 6 * tn], U[0, 6 * tn + 1]))
    N = pt.axial_forces(U[1:], sections, theta)
    Nc, Nt = np.maximum(-N, 0).max(0), np.maximum(N, 0).max(0)
    ratio = stress_ratios(pt.g, Nc, Nt, pt._member_sections(sections))
    return disp, ratio


def sections_from_index(pt, j):
    return {gr: ORDER[int(k)] for gr, k in zip(pt.groups, j)}


def group_index(pt, sections):
    s = pt._member_sections(sections)
    out = np.zeros(len(pt.groups), int)
    for e, nm in enumerate(s):
        out[pt.egroup[e]] = ORDER.index(nm)
    return out


def verdict(ratio, disp, H, disp_limit_ratio=1 / 100.0, r_lim=1.0):
    """验算结论：每杆 (ratio>1 不满足)，整体位移限值 H/100（简化口径）。"""
    return ratio > r_lim, disp > disp_limit_ratio * H
