# -*- coding: utf-8 -*-
"""参数化格构式输电塔生成器（方形塔身 + 三角锥形横担 + 地线支架）。

塔身四角编号 c0(+x,+y)、c1(−x,+y)、c2(−x,−y)、c3(+x,−y)；四面 f0(y+:c0-c1)、f1(x−:c1-c2)、
f2(y−:c2-c3)、f3(x+:c3-c0)。横担沿 ±x（与 PTM 主方向一致）。节间自下而上编号。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import sections as S
from .graph import TrussGraph

CORNER_SIGN = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]], float)
FACES = [(0, 1), (1, 2), (2, 3), (3, 0)]


@dataclass
class ArmTier:
    panel_from_top: int          # 横担所在塔身节间（自塔身顶向下计，0 为最上节间）
    length: float                # 横担外伸长度（自塔身面起）m
    n_panels: int = 4
    tip_half_width: float = 0.35 # 端部下弦半宽
    tip_rise: float = 0.40       # 上弦端点相对下弦高差


@dataclass
class TowerSpec:
    kind: str = "suspension"       # suspension（直线塔）| tension（耐张塔）
    H: float = 58.0                # 塔身顶高 m
    z_waist: float = 36.0          # 变坡点高 m
    half_base: float = 4.6         # 根开之半 m
    half_waist: float = 1.35
    half_top: float = 1.05
    n_lower: int = 8
    n_upper: int = 8
    ratio_lower: float = 0.88      # 节间高度自下而上的公比
    ratio_upper: float = 0.97
    bracing_upper: str = "X"       # X | K
    aux_min_panel_h: float = 2.8   # 节间高度大于此值时布置再分式辅材（过交叉点的水平辅材）
    arms: list = field(default_factory=lambda: [ArmTier(1, 6.2), ArmTier(3, 7.4), ArmTier(5, 6.6)])
    peak_length: float = 2.6       # 地线支架外伸
    peak_rise: float = 1.2
    diaphragm_extra: tuple = ()    # 额外横隔面所在层号
    leg_dz: tuple = (0.0, 0.0, 0.0, 0.0)   # 长短腿：各腿基础高程（负值为加长腿）
    main_schedule: tuple = ("L200x16", "L180x14", "L160x12", "L140x12", "L125x10", "L110x8")
    section_scale: int = 0         # 截面整体升/降档（耐张塔默认 +2）
    seed: int = 0

    @classmethod
    def preset(cls, name: str) -> "TowerSpec":
        if name == "suspension":
            return cls()
        if name == "tension":
            return cls(kind="tension", H=46.0, z_waist=28.0, half_base=5.4, half_waist=1.8, half_top=1.4,
                       n_lower=7, n_upper=7, ratio_lower=0.86, arms=[ArmTier(1, 5.2, 3), ArmTier(3, 6.2, 4),
                                                                      ArmTier(5, 5.6, 3)],
                       section_scale=3, peak_length=2.2)
        if name == "tall":
            return cls(H=78.0, z_waist=50.0, half_base=6.2, half_waist=1.6, half_top=1.2, n_lower=10, n_upper=9,
                       arms=[ArmTier(1, 7.0), ArmTier(3, 8.4, 5), ArmTier(5, 7.4)], section_scale=2)
        if name == "small":
            return cls(H=32.0, z_waist=20.0, half_base=2.8, half_waist=0.9, half_top=0.75, n_lower=5, n_upper=5,
                       arms=[ArmTier(1, 4.0, 3), ArmTier(3, 4.6, 3)], section_scale=-3, peak_length=1.8)
        raise KeyError(name)


def _levels(spec: TowerSpec) -> np.ndarray:
    def geo(total, n, r):
        h0 = total * (1 - r) / (1 - r ** n) if abs(r - 1) > 1e-9 else total / n
        return np.cumsum(h0 * r ** np.arange(n))
    lo = geo(spec.z_waist, spec.n_lower, spec.ratio_lower)
    up = spec.z_waist + geo(spec.H - spec.z_waist, spec.n_upper, spec.ratio_upper)
    return np.concatenate([[0.0], lo, up])


def _half_width(spec: TowerSpec, z: float) -> float:
    if z <= spec.z_waist:
        return spec.half_base + (spec.half_waist - spec.half_base) * z / spec.z_waist
    return spec.half_waist + (spec.half_top - spec.half_waist) * (z - spec.z_waist) / (spec.H - spec.z_waist)


def _closest_mid(p1, p2, q1, q2):
    """两条空间直线 p1p2、q1q2 的最近点中点（近似交点）及两直线上的参数。"""
    d1, d2, r = p2 - p1, q2 - q1, p1 - q1
    a, b, c = d1 @ d1, d1 @ d2, d2 @ d2
    d, e = d1 @ r, d2 @ r
    den = a * c - b * b
    s = (b * e - c * d) / den
    t = (a * e - b * d) / den
    return 0.5 * ((p1 + s * d1) + (q1 + t * d2)), s, t


class _Builder:
    def __init__(self, spec: TowerSpec):
        self.s = spec
        self.g = TrussGraph()
        self.edges = set()

    def node(self, xyz, ntype="node"):
        return self.g.add_node(xyz, ntype)

    def member(self, i, j, cat, part, group, panel=-1, face=-1):
        key = (min(i, j), max(i, j))
        if key in self.edges or i == j:
            return -1
        self.edges.add(key)
        return self.g.add_member(i, j, cat, part, "", "Q235", group, panel, face)


def build_tower(spec: TowerSpec | str = "suspension") -> TrussGraph:
    if isinstance(spec, str):
        spec = TowerSpec.preset(spec)
    B = _Builder(spec)
    z = _levels(spec)
    NL = len(z) - 1
    nl_lo = spec.n_lower
    # ---------------------------------------------------------------- 塔身角点
    corner = {}
    for L, zl in enumerate(z):
        for c in range(4):
            zz = zl + (spec.leg_dz[c] if L == 0 else 0.0)
            hw = _half_width(spec, max(zz, 0.0)) if L > 0 else _half_width(spec, 0.0) + \
                (spec.half_base - spec.half_waist) / spec.z_waist * (-spec.leg_dz[c])
            corner[(L, c)] = B.node([CORNER_SIGN[c, 0] * hw, CORNER_SIGN[c, 1] * hw, zz],
                                    "base" if L == 0 else "corner")
    P = lambda L, c: B.g.nodes[corner[(L, c)]]
    main_mid = {(k, c): [] for k in range(NL) for c in range(4)}   # (z, node)

    def main_point(k, c, zq):
        a, b = P(k, c), P(k + 1, c)
        t = (zq - a[2]) / (b[2] - a[2])
        return a + t * (b - a)

    def get_main_mid(k, c, zq):
        for zz, nid in main_mid[(k, c)]:
            if abs(zz - zq) < 1e-3:
                return nid
        nid = B.node(main_point(k, c, zq), "main_mid")
        main_mid[(k, c)].append((zq, nid))
        return nid

    # ---------------------------------------------------------------- 斜材与辅材
    k_horizontals = set()
    for k in range(NL):
        upper = k >= nl_lo
        pattern = spec.bracing_upper if upper else "X"
        ph = z[k + 1] - z[k]
        seg = "u" if upper else "l"
        for f, (ca, cb) in enumerate(FACES):
            A, Bn, C, D = corner[(k, ca)], corner[(k, cb)], corner[(k + 1, cb)], corner[(k + 1, ca)]
            grp_d = f"body-diag-{seg}{k}"
            if pattern == "X":
                xm, s_, t_ = _closest_mid(P(k, ca), P(k + 1, cb), P(k, cb), P(k + 1, ca))
                X = B.node(xm, "cross")
                for a_, b_ in ((A, X), (X, C), (Bn, X), (X, D)):
                    B.member(a_, b_, "diagonal", "body", grp_d, k, f)
                if ph > spec.aux_min_panel_h:
                    ma = get_main_mid(k, ca, xm[2])
                    mb = get_main_mid(k, cb, xm[2])
                    B.member(ma, X, "auxiliary", "body", f"body-aux-{seg}{k}", k, f)
                    B.member(X, mb, "auxiliary", "body", f"body-aux-{seg}{k}", k, f)
            else:   # K 形：上层面中点
                M = B.node(0.5 * (P(k + 1, ca) + P(k + 1, cb)), "face_mid")
                B.member(A, M, "diagonal", "body", grp_d, k, f)
                B.member(Bn, M, "diagonal", "body", grp_d, k, f)
                B.member(D, M, "auxiliary", "body", f"body-horiz-{seg}{k + 1}", k, f)
                B.member(M, C, "auxiliary", "body", f"body-horiz-{seg}{k + 1}", k, f)
                k_horizontals.add((k + 1, f))
    # ---------------------------------------------------------------- 主材（经中间节点成链）
    for k in range(NL):
        seg = "u" if k >= nl_lo else "l"
        for c in range(4):
            chain = [corner[(k, c)]] + [n for _, n in sorted(main_mid[(k, c)])] + [corner[(k + 1, c)]]
            for a_, b_ in zip(chain[:-1], chain[1:]):
                B.member(a_, b_, "main", "body", f"body-main-{seg}{k}", k, -1)
    # ---------------------------------------------------------------- 横担
    arm_levels = []
    attach = []
    for t_i, arm in enumerate(spec.arms):
        kb = NL - 1 - arm.panel_from_top           # 横担下弦所在层
        kt = kb + 1
        arm_levels += [kb, kt]
        for side in (1, -1):
            cs = (0, 3) if side > 0 else (1, 2)      # (y+, y−) 角点
            rb = [corner[(kb, cs[0])], corner[(kb, cs[1])]]
            rt = [corner[(kt, cs[0])], corner[(kt, cs[1])]]
            hw_b = _half_width(spec, z[kb])
            xb_tip = side * (hw_b + arm.length)
            zb = z[kb]
            tip_b = [np.array([xb_tip, arm.tip_half_width, zb]), np.array([xb_tip, -arm.tip_half_width, zb])]
            tip_t = np.array([xb_tip, 0.0, zb + arm.tip_rise])
            n = arm.n_panels
            bc = [[rb[0]], [rb[1]]]
            tc = [[rt[0]], [rt[1]]]
            for j in range(1, n + 1):
                f = j / n
                for q in range(2):
                    p = B.g.nodes[rb[q]] + f * (tip_b[q] - B.g.nodes[rb[q]])
                    bc[q].append(B.node(p, "arm") if j < n else None)
                for q in range(2):
                    if j < n:
                        p = B.g.nodes[rt[q]] + f * (tip_t - B.g.nodes[rt[q]])
                        tc[q].append(B.node(p, "arm"))
            tb0 = B.node(tip_b[0], "arm_tip"); tb1 = B.node(tip_b[1], "arm_tip")
            bc[0][-1], bc[1][-1] = tb0, tb1
            tt = B.node(tip_t, "arm_tip")
            tc[0].append(tt); tc[1].append(tt)
            gp = f"arm{t_i}"
            for q in range(2):
                for a_, b_ in zip(bc[q][:-1], bc[q][1:]):
                    B.member(a_, b_, "main", "arm", f"{gp}-bc")
                for a_, b_ in zip(tc[q][:-1], tc[q][1:]):
                    B.member(a_, b_, "main", "arm", f"{gp}-tc")
            for j in range(1, n + 1):
                B.member(bc[0][j], bc[1][j], "auxiliary", "arm", f"{gp}-tr")            # 下平面横杆
                if j < n:
                    B.member(tc[0][j], tc[1][j], "auxiliary", "arm", f"{gp}-tr")
                B.member(bc[(j + 1) % 2][j - 1], bc[j % 2][j], "diagonal", "arm", f"{gp}-br")   # 下平面斜杆
                for q in range(2):                                                   # 侧面
                    if j < n:
                        B.member(bc[q][j], tc[q][j], "auxiliary", "arm", f"{gp}-vr")
                    B.member(bc[q][j - 1], tc[q][j], "diagonal", "arm", f"{gp}-sd")
            cn = B.node([xb_tip, 0.0, zb - 0.05], "attach")
            B.member(tb0, cn, "auxiliary", "arm", f"{gp}-tip"); B.member(cn, tb1, "auxiliary", "arm", f"{gp}-tip")
            B.member(cn, tt, "auxiliary", "arm", f"{gp}-tip")
            attach.append({"node": cn, "kind": "conductor", "tier": t_i, "side": side})
    # ---------------------------------------------------------------- 横隔面（变坡点、横担层、塔顶）
    for L in sorted(set([nl_lo, NL] + arm_levels + list(spec.diaphragm_extra))):
        if L <= 0 or L > NL:
            continue
        ids = [corner[(L, c)] for c in range(4)]
        for f, (ca, cb) in enumerate(FACES):
            if (L, f) not in k_horizontals:
                B.member(ids[ca], ids[cb], "auxiliary", "diaphragm", f"dia-h{L}")
        cen = B.node(np.mean(B.g.nodes[ids], axis=0), "dia_center")
        for c in range(4):
            B.member(ids[c], cen, "auxiliary", "diaphragm", f"dia-x{L}")
    # ---------------------------------------------------------------- 地线支架
    for side in (1, -1):
        cs = (0, 3) if side > 0 else (1, 2)
        hw = _half_width(spec, z[NL])
        tip = B.node([side * (hw + spec.peak_length), 0.0, z[NL] + spec.peak_rise], "peak_tip")
        for c in cs:
            B.member(corner[(NL, c)], tip, "main", "peak", "peak-tc")
            B.member(corner[(NL - 1, c)], tip, "diagonal", "peak", "peak-sd")
        attach.append({"node": tip, "kind": "earthwire", "tier": -1, "side": side})
    g = B.g
    g.meta = {"spec": {k: (v if not isinstance(v, (list, tuple)) else [a.__dict__ if isinstance(a, ArmTier) else a
                                                                           for a in v])
                       for k, v in spec.__dict__.items()},
              "levels": z.tolist(), "base_nodes": [corner[(0, c)] for c in range(4)], "attach": attach,
              "attachments": [], "H_total": float(np.max(g.nodes[:, 2]))}
    assign_sections(g, spec)
    return g


def assign_sections(g: TrussGraph, spec: TowerSpec) -> None:
    """按“主材随高度递减 + 斜/辅材按长细比最轻”规则赋截面与材质（模拟设计院常规选材）。"""
    L = g.lengths()
    H = max(spec.H, 1.0)
    sched = [S.step(s, spec.section_scale) for s in spec.main_schedule]
    cuts = np.linspace(0, 1, len(sched) + 1)[1:-1]
    for e in range(g.n_members):
        cat, part = g.cat[e], g.part[e]
        zm = 0.5 * (g.nodes[g.mi[e], 2] + g.nodes[g.mj[e], 2])
        if part == "body" and cat == "main":
            name = sched[int(np.searchsorted(cuts, zm / H))]
            a = S.angle(name)
            while L[e] / a.iv > S.LAMBDA_LIMIT["main"]:
                name = S.step(name, 1); a = S.angle(name)
            g.sec[e], g.mat[e] = name, "Q355"
        elif part in ("arm", "peak") and cat == "main":
            base = "L125x10" if part == "arm" and g.group[e].endswith("bc") else "L100x8"
            name = S.step(base, spec.section_scale // 2)
            while L[e] / S.angle(name).iv > S.LAMBDA_LIMIT["main"]:
                name = S.step(name, 1)
            g.sec[e], g.mat[e] = name, "Q355"
        else:
            lim = S.LAMBDA_LIMIT["diagonal" if cat == "diagonal" else "auxiliary"]
            bmin = 0.056 if cat == "diagonal" else 0.045
            if cat == "diagonal" and part == "body" and zm < spec.z_waist * 0.5:
                bmin = 0.075
            a = S.lightest(lambda a: a.b >= bmin - 1e-9 and L[e] / a.iv <= lim)
            name = S.step(a.name, max(0, spec.section_scale // 2))
            g.sec[e], g.mat[e] = name, "Q235"


# ====================================================================== 损伤与非对称
def remove_members(g: TrussGraph, idx) -> TrussGraph:
    return g.remove_members(idx, drop_orphans=True)


def random_missing(g: TrussGraph, cat: str, n: int, rng=None, part="body") -> list:
    rng = np.random.default_rng(rng)
    cand = np.flatnonzero(g.mask(cat=cat, part=part))
    return sorted(rng.choice(cand, size=min(n, len(cand)), replace=False).tolist())


def bend_members(g: TrussGraph, idx, offset: float, rng=None) -> None:
    """杆件中点按垂直杆轴的随机方向偏移 offset（m），模拟弯曲损伤（不改变拓扑）。"""
    rng = np.random.default_rng(rng)
    for e in np.atleast_1d(idx):
        d = g.nodes[g.mj[e]] - g.nodes[g.mi[e]]
        d /= np.linalg.norm(d)
        v = rng.normal(size=3); v -= (v @ d) * d; v /= np.linalg.norm(v)
        g.bend[e] = tuple((offset * v).tolist())


def add_attachment(g: TrussGraph, center, size=0.6, kind="bird_nest") -> None:
    g.meta.setdefault("attachments", []).append({"center": list(map(float, center)), "size": float(size), "kind": kind})


def tower_mass(g: TrussGraph, factor: float = 1.0) -> float:
    L = g.lengths()
    return float(factor * sum(S.angle(s).mass * l for s, l in zip(g.sec, L)))
