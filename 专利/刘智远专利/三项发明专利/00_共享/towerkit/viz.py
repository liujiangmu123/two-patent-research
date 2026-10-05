# -*- coding: utf-8 -*-
"""绘图：塔线框（彩色按类别 / 黑白线条专利附图模式）、点云、振型。"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Line3DCollection  # noqa: E402

from .graph import TrussGraph  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = {"main": "#C0392B", "diagonal": "#2E5E8C", "auxiliary": "#222222"}
WIDTH_BW = {"main": 1.6, "diagonal": 0.9, "auxiliary": 0.6}


def plot_truss(ax, g: TrussGraph, bw: bool = False, disp=None, scale: float = 1.0, alpha=1.0, lw_scale=1.0,
               mask=None):
    X = g.nodes if disp is None else g.nodes + scale * disp
    for c in ("auxiliary", "diagonal", "main"):
        m = np.asarray(g.cat) == c
        if mask is not None:
            m &= mask
        if not m.any():
            continue
        i, j = np.asarray(g.mi)[m], np.asarray(g.mj)[m]
        seg = np.stack([X[i], X[j]], axis=1)
        col = "black" if bw else COLORS[c]
        lw = (WIDTH_BW[c] if bw else {"main": 1.4, "diagonal": 0.8, "auxiliary": 0.5}[c]) * lw_scale
        ax.add_collection3d(Line3DCollection(seg, colors=col, linewidths=lw, alpha=alpha))
    set_equal(ax, X)
    return ax


def plot_points(ax, xyz, c="#3A7D44", s=0.3, alpha=0.6):
    ax.scatter(xyz[:, 0], xyz[:, 1], xyz[:, 2], s=s, c=c, alpha=alpha, linewidths=0)
    return ax


def set_equal(ax, X):
    lo, hi = X.min(axis=0), X.max(axis=0)
    c = (lo + hi) / 2
    r = (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(max(c[2] - r, lo[2] - 1), c[2] + r)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass


def new3d(figsize=(6, 8), elev=12, azim=-60, bw=False):
    fig = plt.figure(figsize=figsize, dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)
    if bw:
        ax.set_axis_off()
    return fig, ax
