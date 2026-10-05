# -*- coding: utf-8 -*-
"""有限元灵敏度 → 杆件结构重要性权重。

  * 塔顶位移灵敏度（伴随法）：δ = cᵀu，Ku = F，Kᵀλ = c，∂δ/∂ln k_e = −λ_eᵀ K_e u_e；
  * 模态频率灵敏度：∂ω_i²/∂ln k_e = φ_i,eᵀ K_e φ_i,e（质量归一化振型）；
  * 权重 w_e = w0 + (1−w0)·[α·|Sδ_e|/max + (1−α)·Σ_i |Sf_i,e|/max]，取 [w0,1]。
"""
from __future__ import annotations

import numpy as np

from ._tk import fem, loads


def design_load(model, w0=500.0, direction=(0.0, 1.0, 0.0)):
    F = loads.wind_static(model, w0=w0, direction=direction)
    F += loads.conductor_loads(model, vertical=25e3, transverse=8e3)
    return F


def tip_selector(model, direction=(0.0, 1.0, 0.0)):
    g = model.g
    top = [a["node"] for a in g.meta["attach"] if a["kind"] == "earthwire"]
    c = np.zeros(model.ndof)
    d = np.asarray(direction, float); d /= np.linalg.norm(d)
    for n in top:
        c[6 * n:6 * n + 3] += d / len(top)
    return c


def element_energy_terms(model, u, v):
    """每单元 v_eᵀ K_e u_e（全局坐标）。"""
    p = model.p
    out = np.zeros(len(model.L))
    for e in range(len(model.L)):
        T = model._T(e)
        kl = fem.k_local(p.E[e], p.G[e], p.A[e], p.I[e], p.I[e], p.J[e], model.L[e], model.truss)
        d = model.dofs(e)
        out[e] = v[d] @ (T.T @ kl @ T) @ u[d]
    return out


def sensitivities(g, n_modes=3, direction=(0.0, 1.0, 0.0)):
    m = fem.FEModel(g).fix_base()
    F = design_load(m, direction=direction)
    u = m.solve_static(F)
    c = tip_selector(m, direction)
    lam = m.solve_static(c)
    tip = float(c @ u)
    s_tip = -element_energy_terms(m, u, lam)
    freq, phi = m.modes(n_modes)
    s_f = np.zeros((n_modes, g.n_members))
    for i in range(n_modes):
        w2 = (2 * np.pi * freq[i]) ** 2
        s_f[i] = element_energy_terms(m, phi[:, i], phi[:, i]) / (2 * w2) * freq[i]  # ∂f/∂ln k
    return {"tip": tip, "s_tip": s_tip, "freq": freq, "s_f": s_f}


def importance_weights(g, alpha=0.6, w0=0.05, n_modes=3, sens=None):
    s = sens or sensitivities(g, n_modes)
    a = np.abs(s["s_tip"]); a /= max(a.max(), 1e-30)
    b = np.abs(s["s_f"]).sum(0); b /= max(b.max(), 1e-30)
    r = alpha * a + (1 - alpha) * b
    r /= max(r.max(), 1e-30)
    # 压缩动态范围（平方根），避免极少数主材垄断
    return w0 + (1 - w0) * np.sqrt(r), s
