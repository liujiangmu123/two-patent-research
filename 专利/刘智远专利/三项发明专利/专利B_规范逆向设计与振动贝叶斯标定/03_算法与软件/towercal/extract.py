# -*- coding: utf-8 -*-
"""由杆件级桁架模型（TrussGraph）自动提取规范设计输入。

只使用几何与拓扑信息（节点坐标、杆件类别/部位/分组、导地线挂点），不使用截面信息。
绝缘子串长度、相邻塔位等可由任意测量手段（激光点云、影像、台账）获得，作为可选观测输入。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np

# 电压等级规则表：悬垂绝缘子串长度区间（m，含金具）、代表档距（m）、导线参数
#   d: 子导线外径 m；w: 子导线单位重 kg/m；n_sub: 分裂数；T: 子导线最大使用张力 N；
#   m_ins: 绝缘子串+金具质量 kg；Lrep: 代表档距 m
VOLTAGE_TABLE = [
    {"kV": 110, "ins": (1.0, 1.9), "d": 0.0216, "w": 0.866, "n_sub": 1, "T": 2.6e4, "m_ins": 60.0, "Lrep": 300.0},
    {"kV": 220, "ins": (1.9, 3.2), "d": 0.0268, "w": 1.349, "n_sub": 2, "T": 3.6e4, "m_ins": 180.0, "Lrep": 400.0},
    {"kV": 330, "ins": (3.2, 4.3), "d": 0.0268, "w": 1.349, "n_sub": 2, "T": 3.8e4, "m_ins": 320.0, "Lrep": 450.0},
    {"kV": 500, "ins": (4.3, 6.6), "d": 0.0300, "w": 1.511, "n_sub": 4, "T": 4.0e4, "m_ins": 600.0, "Lrep": 500.0},
    {"kV": 750, "ins": (6.6, 9.5), "d": 0.0300, "w": 1.511, "n_sub": 6, "T": 4.2e4, "m_ins": 1100.0, "Lrep": 550.0},
]
EARTHWIRE = {"d": 0.0135, "w": 0.70, "T": 1.8e4, "m_ins": 15.0}


@dataclass
class DesignInput:
    height_total: float                 # 全高 m
    call_height: float                  # 呼高（最低导线挂点高度）m
    root_open: float                    # 根开 m
    arm_lengths: list                   # 各层横担挂点至塔中心水平距离 m
    n_conductor_points: int
    n_earthwire_points: int
    n_circuits: int
    insulator_len: float                # 绝缘子串长 m（观测值或缺省推断）
    voltage_kV: int
    voltage_conf: float                 # 规则匹配置信度 0~1
    tower_type: str                     # suspension | tension
    line_angle_deg: float               # 线路转角（未知时取规则缺省）
    span_h: float                       # 水平档距 m
    span_v: float                       # 垂直档距 m
    attach_nodes: list = field(default_factory=list)
    earth_nodes: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @property
    def wire(self):
        return next(v for v in VOLTAGE_TABLE if v["kV"] == self.voltage_kV)


def _voltage_from_insulator(L_ins: float, phase_sep: float):
    """按串长查规则表；以相间水平距离（同层两挂点距离的一半）做一致性校核，返回 (kV, 置信度)。"""
    best, conf = None, 0.0
    for v in VOLTAGE_TABLE:
        lo, hi = v["ins"]
        if lo <= L_ins < hi:
            mid, half = 0.5 * (lo + hi), 0.5 * (hi - lo)
            best, conf = v, 1.0 - 0.5 * abs(L_ins - mid) / half
    if best is None:
        best = VOLTAGE_TABLE[0] if L_ins < 1.0 else VOLTAGE_TABLE[-1]
        conf = 0.3
    # 相间距经验下限（m）：110:3.5 220:5.5 330:7 500:9 750:12（相对横担挂点间距的一致性校核）
    need = {110: 3.5, 220: 5.5, 330: 7.0, 500: 9.0, 750: 12.0}[best["kV"]]
    if phase_sep < 0.7 * need:
        conf *= 0.6
    return best["kV"], float(np.clip(conf, 0.0, 1.0))


def extract_design_input(g, insulator_len: float | None = None, neighbor_xy=None, insulator_orient=None) -> DesignInput:
    """从桁架图提取设计输入。

    g: towerkit.TrussGraph（需 meta['attach']，或节点类型 'attach'/'peak_tip'）。
    insulator_len: 观测的绝缘子串长度；缺省时取 g.meta['attach'][*]['insulator_len'] 的中位数，
                   再缺省按横担长度经验关系 L_ins ≈ 0.38·横担长 推断（置信度降低）。
    neighbor_xy: 相邻两基塔的平面坐标 [(x,y)_前, (x,y)_后]（可选），用于计算转角与档距。
    insulator_orient: 'vertical'（悬垂）| 'horizontal'（耐张）| None（未知）。
    """
    X = np.asarray(g.nodes, float)
    notes = []
    att = g.meta.get("attach") or []
    if not att:
        att = [{"node": i, "kind": "conductor" if t == "attach" else "earthwire"}
               for i, t in enumerate(g.ntype) if t in ("attach", "peak_tip")]
    cnodes = [a["node"] for a in att if a["kind"] == "conductor"]
    enodes = [a["node"] for a in att if a["kind"] == "earthwire"]
    H = float(X[:, 2].max() - X[:, 2].min())
    base = g.meta.get("base_nodes") or list(np.argsort(X[:, 2])[:4])
    xb = X[base]
    root = float(np.mean([np.ptp(xb[:, 0]), np.ptp(xb[:, 1])]))
    cz = X[cnodes, 2]
    call_h = float(cz.min()) if len(cnodes) else 0.0
    # 横担层：按挂点高度聚类
    tiers = []
    for nd in sorted(cnodes, key=lambda n: X[n, 2]):
        if tiers and abs(X[nd, 2] - X[tiers[-1][0], 2]) < 0.5:
            tiers[-1].append(nd)
        else:
            tiers.append([nd])
    arm_len = [float(np.mean(np.hypot(X[t, 0], X[t, 1]))) for t in tiers]
    n_circ = 2 if all(len(t) >= 2 for t in tiers) and len(cnodes) >= 6 else 1
    phase_sep = float(np.mean([np.ptp(X[t, 0]) / 2 for t in tiers])) if tiers else 0.0
    if insulator_len is None:
        vals = [a.get("insulator_len") for a in att if a["kind"] == "conductor" and a.get("insulator_len")]
        if vals:
            insulator_len = float(np.median(vals))
            notes.append("绝缘子串长取挂点观测中位数")
        else:
            insulator_len = 0.38 * float(np.mean(arm_len))
            notes.append("无串长观测，按横担长经验关系推断")
    kv, conf = _voltage_from_insulator(insulator_len, phase_sep)
    if "推断" in "".join(notes):
        conf *= 0.6
    if insulator_orient is None:
        orients = [a.get("insulator_orient") for a in att if a.get("insulator_orient")]
        insulator_orient = orients[0] if orients else None
    # 转角与档距
    rep = next(v for v in VOLTAGE_TABLE if v["kV"] == kv)["Lrep"]
    angle = 0.0
    span_h = span_v = rep
    if neighbor_xy is not None:
        p0, p1 = np.asarray(neighbor_xy[0], float), np.asarray(neighbor_xy[1], float)
        v0, v1 = -p0, p1                     # 本塔在原点：来向 p0→0、去向 0→p1
        l0, l1 = np.linalg.norm(v0), np.linalg.norm(v1)
        angle = float(np.degrees(np.arccos(np.clip(v0 @ v1 / (l0 * l1), -1, 1))))   # 线路偏转角
        span_h = 0.5 * (l0 + l1)
        span_v = 1.25 * span_h
        notes.append("转角与档距由相邻塔位计算")
    else:
        span_v = 1.25 * rep
    ratio = root / max(H, 1e-6)
    if angle > 3.0 or insulator_orient == "horizontal":
        ttype = "tension"
    elif insulator_orient == "vertical" and angle <= 3.0:
        ttype = "suspension"
    else:
        ttype = "tension" if ratio > 0.20 else "suspension"
        notes.append(f"塔型由根开/全高比 {ratio:.3f} 判定")
    if ttype == "tension" and neighbor_xy is None:
        angle = 30.0
        notes.append("耐张塔转角未知，取规则缺省 30°（先验情景中按 0–60° 混合）")
    return DesignInput(height_total=H, call_height=call_h, root_open=root, arm_lengths=arm_len,
                       n_conductor_points=len(cnodes), n_earthwire_points=len(enodes), n_circuits=n_circ,
                       insulator_len=float(insulator_len), voltage_kV=kv, voltage_conf=conf, tower_type=ttype,
                       line_angle_deg=angle, span_h=float(span_h), span_v=float(span_v),
                       attach_nodes=[int(c) for c in cnodes], earth_nodes=[int(e) for e in enodes], notes=notes)


def attach_masses(di: DesignInput) -> dict:
    """挂点附加质量（绝缘子串 + 金具），kg。"""
    w = di.wire
    out = {n: w["m_ins"] for n in di.attach_nodes}
    out.update({n: EARTHWIRE["m_ins"] for n in di.earth_nodes})
    return out
