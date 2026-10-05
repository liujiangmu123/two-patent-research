# -*- coding: utf-8 -*-
"""杆件级桁架图 TrussGraph 与 PTM 同口径的重建评价指标。

坐标：右手系，x 为横担方向，z 竖直向上，原点为塔位地面中心；单位 m。
杆件类别 category ∈ {main, diagonal, auxiliary}（与 PTM 的主材/斜材/辅材一致），
部位 part ∈ {body, arm, peak, diaphragm}。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

CATS = ("main", "diagonal", "auxiliary")


@dataclass
class TrussGraph:
    nodes: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    ntype: list = field(default_factory=list)
    mi: list = field(default_factory=list)
    mj: list = field(default_factory=list)
    cat: list = field(default_factory=list)
    part: list = field(default_factory=list)
    sec: list = field(default_factory=list)
    mat: list = field(default_factory=list)
    group: list = field(default_factory=list)
    panel: list = field(default_factory=list)
    face: list = field(default_factory=list)
    bend: list = field(default_factory=list)       # 每杆中点偏移向量（弯曲损伤），默认 0
    meta: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- 构建
    def add_node(self, xyz, ntype: str = "node") -> int:
        self.nodes = np.vstack([self.nodes, np.asarray(xyz, float).reshape(1, 3)])
        self.ntype.append(ntype)
        return len(self.ntype) - 1

    def add_member(self, i, j, cat, part="body", sec="", mat="Q235", group="", panel=-1, face=-1) -> int:
        if i == j:
            raise ValueError("杆件两端节点相同")
        self.mi.append(int(i)); self.mj.append(int(j)); self.cat.append(cat); self.part.append(part)
        self.sec.append(sec); self.mat.append(mat); self.group.append(group)
        self.panel.append(int(panel)); self.face.append(int(face)); self.bend.append((0.0, 0.0, 0.0))
        return len(self.mi) - 1

    # ---------------------------------------------------------------- 属性
    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_members(self) -> int:
        return len(self.mi)

    def ends(self):
        return np.asarray(self.mi, int), np.asarray(self.mj, int)

    def segments(self) -> np.ndarray:
        i, j = self.ends()
        return np.stack([self.nodes[i], self.nodes[j]], axis=1)

    def lengths(self) -> np.ndarray:
        s = self.segments()
        return np.linalg.norm(s[:, 1] - s[:, 0], axis=1)

    def mask(self, cat=None, part=None) -> np.ndarray:
        m = np.ones(self.n_members, bool)
        if cat is not None:
            m &= np.isin(np.asarray(self.cat), np.atleast_1d(cat))
        if part is not None:
            m &= np.isin(np.asarray(self.part), np.atleast_1d(part))
        return m

    def counts(self) -> dict:
        out = {c: int(np.sum(np.asarray(self.cat) == c)) for c in CATS}
        out["nodes"] = self.n_nodes
        out["members"] = self.n_members
        return out

    def adjacency(self) -> dict:
        adj = {k: [] for k in range(self.n_nodes)}
        for e, (a, b) in enumerate(zip(self.mi, self.mj)):
            adj[a].append(e); adj[b].append(e)
        return adj

    # ---------------------------------------------------------------- 编辑
    def copy(self) -> "TrussGraph":
        return TrussGraph.from_dict(self.to_dict())

    def remove_members(self, idx, drop_orphans: bool = True) -> "TrussGraph":
        keep = np.ones(self.n_members, bool)
        keep[np.asarray(list(idx), int)] = False
        g = TrussGraph(nodes=self.nodes.copy(), ntype=list(self.ntype), meta=json.loads(json.dumps(self.meta)))
        for e in np.flatnonzero(keep):
            k = g.add_member(self.mi[e], self.mj[e], self.cat[e], self.part[e], self.sec[e], self.mat[e],
                             self.group[e], self.panel[e], self.face[e])
            g.bend[k] = tuple(self.bend[e])
        return g.drop_orphans() if drop_orphans else g

    def drop_orphans(self) -> "TrussGraph":
        used = np.zeros(self.n_nodes, bool)
        used[self.mi] = True; used[self.mj] = True
        for k in self.meta.get("base_nodes", []):
            used[k] = True
        new = -np.ones(self.n_nodes, int)
        new[used] = np.arange(used.sum())
        g = TrussGraph(nodes=self.nodes[used].copy(), ntype=[t for t, u in zip(self.ntype, used) if u],
                       meta=json.loads(json.dumps(self.meta)))
        for key in ("base_nodes",):
            if key in g.meta:
                g.meta[key] = [int(new[k]) for k in g.meta[key]]
        if "attach" in g.meta:
            g.meta["attach"] = [dict(a, node=int(new[a["node"]])) for a in g.meta["attach"] if new[a["node"]] >= 0]
        for e in range(self.n_members):
            k = g.add_member(new[self.mi[e]], new[self.mj[e]], self.cat[e], self.part[e], self.sec[e], self.mat[e],
                             self.group[e], self.panel[e], self.face[e])
            g.bend[k] = tuple(self.bend[e])
        return g

    def merge_close_nodes(self, tol: float = 1e-3) -> "TrussGraph":
        tree = cKDTree(self.nodes)
        pairs = tree.query_pairs(tol)
        parent = np.arange(self.n_nodes)

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for a, b in pairs:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        root = np.array([find(a) for a in range(self.n_nodes)])
        uniq, inv = np.unique(root, return_inverse=True)
        g = TrussGraph(nodes=self.nodes[uniq].copy(), ntype=[self.ntype[u] for u in uniq],
                       meta=json.loads(json.dumps(self.meta)))
        if "base_nodes" in g.meta:
            g.meta["base_nodes"] = [int(inv[k]) for k in g.meta["base_nodes"]]
        if "attach" in g.meta:
            g.meta["attach"] = [dict(a, node=int(inv[a["node"]])) for a in g.meta["attach"]]
        seen = set()
        for e in range(self.n_members):
            a, b = int(inv[self.mi[e]]), int(inv[self.mj[e]])
            if a == b or (min(a, b), max(a, b)) in seen:
                continue
            seen.add((min(a, b), max(a, b)))
            k = g.add_member(a, b, self.cat[e], self.part[e], self.sec[e], self.mat[e], self.group[e],
                             self.panel[e], self.face[e])
            g.bend[k] = tuple(self.bend[e])
        return g

    # ---------------------------------------------------------------- 序列化
    def to_dict(self) -> dict:
        return {"nodes": self.nodes.tolist(), "ntype": self.ntype,
                "members": [{"i": a, "j": b, "cat": c, "part": p, "sec": s, "mat": m, "group": g, "panel": pn,
                             "face": f, "bend": list(bd)} for a, b, c, p, s, m, g, pn, f, bd in
                            zip(self.mi, self.mj, self.cat, self.part, self.sec, self.mat, self.group, self.panel,
                                self.face, self.bend)],
                "meta": self.meta}

    @classmethod
    def from_dict(cls, d: dict) -> "TrussGraph":
        g = cls(nodes=np.asarray(d["nodes"], float).reshape(-1, 3), ntype=list(d.get("ntype", [])),
                meta=json.loads(json.dumps(d.get("meta", {}))))
        if len(g.ntype) < g.n_nodes:
            g.ntype += ["node"] * (g.n_nodes - len(g.ntype))
        for m in d["members"]:
            k = g.add_member(m["i"], m["j"], m["cat"], m.get("part", "body"), m.get("sec", ""), m.get("mat", "Q235"),
                             m.get("group", ""), m.get("panel", -1), m.get("face", -1))
            g.bend[k] = tuple(m.get("bend", (0, 0, 0)))
        return g

    def save_json(self, path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False)

    @classmethod
    def load_json(cls, path) -> "TrussGraph":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


# ====================================================================== 评价指标（与 PTM 口径一致）
def match_nodes(gt: np.ndarray, rec: np.ndarray, thr: float = 0.5):
    """全局一一最近匹配（匈牙利算法，超过阈值的配对丢弃）。返回 (gt_idx, rec_idx, dist)。"""
    if len(gt) == 0 or len(rec) == 0:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
    d = np.linalg.norm(gt[:, None, :] - rec[None, :, :], axis=2)
    big = 1e6
    cost = np.where(d <= thr, d, big)
    r, c = linear_sum_assignment(cost)
    ok = cost[r, c] < big
    return r[ok], c[ok], d[r[ok], c[ok]]


def evaluate(gt: TrussGraph, rec: TrussGraph, thr: float = 0.5) -> dict:
    """返回 RMSEn、分类别 NGED、杆件召回率/精确率（类别须一致才算正确）。"""
    gi, ri, dist = match_nodes(gt.nodes, rec.nodes, thr)
    r2g = {int(r): int(g) for g, r in zip(gi, ri)}
    out = {"RMSEn": float(np.sqrt(np.mean(dist ** 2))) if len(dist) else float("nan"),
           "matched_nodes": int(len(gi)), "gt_nodes": gt.n_nodes, "rec_nodes": rec.n_nodes}
    gt_edges = {}
    for e, (a, b, c) in enumerate(zip(gt.mi, gt.mj, gt.cat)):
        gt_edges[(min(a, b), max(a, b))] = c
    tot = {"FPv": 0, "FNv": 0, "FPe": 0, "FNe": 0, "V": 0, "E": 0}
    for c in CATS:
        vg = {k for a, b, cc in zip(gt.mi, gt.mj, gt.cat) if cc == c for k in (a, b)}
        vr = {k for a, b, cc in zip(rec.mi, rec.mj, rec.cat) if cc == c for k in (a, b)}
        eg = {(min(a, b), max(a, b)) for a, b, cc in zip(gt.mi, gt.mj, gt.cat) if cc == c}
        tp = set()
        fpe = 0
        for a, b, cc in zip(rec.mi, rec.mj, rec.cat):
            if cc != c:
                continue
            ga, gb = r2g.get(a), r2g.get(b)
            key = (min(ga, gb), max(ga, gb)) if ga is not None and gb is not None else None
            if key is not None and gt_edges.get(key) == c:
                tp.add(key)
            else:
                fpe += 1
        fne = len(eg - tp)
        fpv = sum(1 for k in vr if r2g.get(k) not in vg)
        matched_g = {r2g[k] for k in vr if k in r2g}
        fnv = sum(1 for k in vg if k not in matched_g)
        denom = len(vg) + len(eg)
        out[f"NGED_{c}"] = (fpv + fnv + fpe + fne) / denom if denom else float("nan")
        out[f"recall_{c}"] = len(tp) / len(eg) if eg else float("nan")
        nrec = sum(1 for cc in rec.cat if cc == c)
        out[f"precision_{c}"] = len(tp) / nrec if nrec else float("nan")
        for k, v in (("FPv", fpv), ("FNv", fnv), ("FPe", fpe), ("FNe", fne), ("V", len(vg)), ("E", len(eg))):
            tot[k] += v
    out["NGED_all"] = (tot["FPv"] + tot["FNv"] + tot["FPe"] + tot["FNe"]) / max(1, tot["V"] + tot["E"])
    return out


def point_segment_distance(points: np.ndarray, seg: np.ndarray, chunk: int = 4000) -> np.ndarray:
    """每个点到线段集合的最短距离（向量化分块）。seg: (M,2,3)。"""
    a = seg[:, 0]; ab = seg[:, 1] - seg[:, 0]
    ab2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-12)
    out = np.empty(len(points))
    for s in range(0, len(points), chunk):
        p = points[s:s + chunk]
        ap = p[:, None, :] - a[None, :, :]
        t = np.clip(np.einsum("nmk,mk->nm", ap, ab) / ab2, 0.0, 1.0)
        d = ap - t[..., None] * ab[None]
        out[s:s + chunk] = np.sqrt(np.min(np.einsum("nmk,nmk->nm", d, d), axis=1))
    return out


def point_to_model(points: np.ndarray, g: TrussGraph) -> dict:
    d = point_segment_distance(points, g.segments())
    return {"RMSEp": float(np.sqrt(np.mean(d ** 2))), "PP0.2": float(np.mean(d < 0.2)), "d": d}
