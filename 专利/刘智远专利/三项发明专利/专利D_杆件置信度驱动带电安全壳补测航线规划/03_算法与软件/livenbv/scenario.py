# -*- coding: utf-8 -*-
"""合成场景：设计先验塔（名义对称）、真值塔（施工偏差/倾斜/高低腿/缺材/遮挡物）、带电导线、初始航线。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._tk import lidar as L
from ._tk import tk

VARIANTS = ("standard", "highlow", "missing", "occluded", "combined")


@dataclass
class Scenario:
    name: str
    prior: object                 # 设计先验 TrussGraph（名义对称，规划用）
    gt: object                    # 真值 TrussGraph（与 prior 同节点编号；缺材已删除）
    gt_member_exists: np.ndarray  # (n_members_prior,) 真值是否存在该杆件
    geom_gt: object               # 真值扫描几何（含遮挡物）
    geom_plan: object             # 规划几何（先验，无遮挡物）
    live: list                    # 带电体线段 [(p0,p1,kind)]
    grounded: list                # 接地导体（地线）线段
    voltage_kv: float = 220.0
    meta: dict = field(default_factory=dict)


def build_prior(preset="suspension"):
    return tk.build_tower(preset)


def make_scenario(variant="standard", preset="suspension", seed=0, voltage_kv=220.0, string_len=3.0,
                  span_half=120.0) -> Scenario:
    rng = np.random.default_rng(seed)
    prior = build_prior(preset)
    gt = prior.copy()
    X = gt.nodes.copy()
    H = float(X[:, 2].max())
    # 施工偏差：节点 2 cm 随机 + 整体倾斜（塔顶 0.12 m）
    X += rng.normal(0, 0.02, X.shape)
    lean = rng.normal(size=2); lean = 0.12 * lean / np.linalg.norm(lean)
    X[:, :2] += np.outer(X[:, 2] / H, lean)
    base = prior.meta["base_nodes"]
    X[base] = prior.nodes[base]  # 基础按设计（随后高低腿再改）
    exists = np.ones(prior.n_members, bool)
    attachments = []
    if variant in ("highlow", "combined"):
        for c, dz in ((1, -1.5), (3, -0.8)):
            n = base[c]
            xy = prior.nodes[n, :2]
            X[n, 2] += dz
            X[n, :2] = xy * (1 + (-dz) * 0.07 / np.linalg.norm(xy) * np.sqrt(2))
    if variant in ("missing", "combined"):
        cat = np.asarray(prior.cat); part = np.asarray(prior.part); pan = np.asarray(prior.panel)
        cand = np.flatnonzero((cat == "diagonal") & (part == "body") & (pan >= 0) & (pan <= 5))
        miss = rng.choice(cand, 6, replace=False).tolist()
        cand2 = np.flatnonzero((cat == "diagonal") & (part == "arm"))
        miss += rng.choice(cand2, 2, replace=False).tolist()
        exists[miss] = False
    if variant in ("occluded", "combined"):
        # 塔脚植被/杂物遮挡 + 横担鸟巢
        for c in (0, 2):
            p = prior.nodes[base[c]]
            attachments.append({"center": [p[0] * 1.05, p[1] * 1.05, 1.1], "size": 2.4, "kind": "vegetation"})
        attachments.append({"center": [2.6, 3.4, 1.0], "size": 2.0, "kind": "vegetation"})
        tip = [a for a in prior.meta["attach"] if a["kind"] == "conductor"][2]
        q = prior.nodes[tip["node"]]
        attachments.append({"center": [q[0] * 0.75, 0.0, q[2] + 0.4], "size": 0.9, "kind": "bird_nest"})
    gt.nodes = X
    gt2 = gt.remove_members(np.flatnonzero(~exists), drop_orphans=False)
    gt2.meta["attachments"] = attachments
    geom_gt = L.build_geometry(gt2, include_attachments=True)
    geom_plan = L.build_geometry(prior, include_attachments=False)
    live, grounded = line_geometry(prior, string_len, span_half)
    return Scenario(variant, prior, gt2, exists, geom_gt, geom_plan, live, grounded, voltage_kv,
                    {"lean": lean.tolist(), "attachments": attachments, "missing": np.flatnonzero(~exists).tolist(),
                     "H": H})


def line_geometry(g, string_len=3.0, span_half=120.0):
    """导线（带电）：悬垂串下端导线沿 y 方向直线延伸；绝缘子串整体保守视为带电体。地线视为接地导体。"""
    live, grounded = [], []
    for a in g.meta["attach"]:
        p = g.nodes[a["node"]].copy()
        if a["kind"] == "conductor":
            q = p - np.array([0, 0, string_len])
            live.append((q + [0, -span_half, 0], q + [0, span_half, 0], "conductor"))
            live.append((p, q, "insulator"))
        else:
            grounded.append((p + [0, -span_half, 0], p + [0, span_half, 0], "earthwire"))
    return live, grounded


def mirror_maps(g, tol=0.05):
    """名义塔关于 x=0、y=0 平面的节点镜像映射与杆件镜像映射（-1 表示无对应）。"""
    X = g.nodes
    from scipy.spatial import cKDTree
    tr = cKDTree(X)
    maps_n = []
    for s in ((-1, 1, 1), (1, -1, 1), (-1, -1, 1)):
        d, j = tr.query(X * np.asarray(s))
        maps_n.append(np.where(d < tol, j, -1))
    key = {(min(a, b), max(a, b)): e for e, (a, b) in enumerate(zip(g.mi, g.mj))}
    maps_e = []
    for mn in maps_n:
        me = np.full(g.n_members, -1)
        for e, (a, b) in enumerate(zip(g.mi, g.mj)):
            ia, ib = mn[a], mn[b]
            if ia >= 0 and ib >= 0:
                me[e] = key.get((min(ia, ib), max(ia, ib)), -1)
        maps_e.append(me)
    return maps_n, maps_e


# ---------------------------------------------------------------- 初始常规航线（PTM 式双倾角扫描）
def initial_flight(sc: Scenario, clearance=18.0, tilt_deg=30.0, speed=6.0, half_len=55.0):
    """沿线路方向（y）于塔顶上方 clearance 处直线飞越；载荷双倾角：视轴自铅垂向左/右倾 tilt。"""
    H = sc.meta["H"]
    z = H + clearance
    tr = L.line_path([0.0, -half_len, z], [0.0, half_len, z], speed=speed)
    mounts = [L.Mount(yaw=90, pitch=-(90 - tilt_deg)), L.Mount(yaw=-90, pitch=-(90 - tilt_deg))]
    return tr, mounts
