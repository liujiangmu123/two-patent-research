# -*- coding: utf-8 -*-
"""规范逆向设计：DL/T 5486 / GB 50017 荷载组合 + 稳定、长细比约束下的分组离散截面优化，及截面先验离散分布。

离散优化采用“分组满应力准则迭代 + 离散档位上的最轻可行截面选择”：每轮以当前截面做多工况有限元分析，
对每个对称/面板分组在角钢目录（按面积升序）中选满足全部约束的最轻规格，直到截面不再变化。
该求解器可替换为任意离散优化器（如 ISSA、遗传算法），不影响先验构造流程。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from towerkit import sections as S
from towerkit import loads as TL
from towerkit.fem import FEModel, props_from_graph

from .extract import DesignInput, VOLTAGE_TABLE, EARTHWIRE, attach_masses

G_ACC = 9.81
RHO_ICE = 900.0
#: 各类杆件最小规格（DL/T 5486：受力材不小于 L45×4，主材不小于 L63×5）
MIN_SECTION = {"main": "L63x5", "diagonal": "L45x4", "auxiliary": "L40x4"}


@dataclass
class Scenario:
    """一组设计输入情景（由提取结果 + 不可观测量的取值组成）。"""
    v0: float = 27.0          # 基本风速 m/s（10 m 高、50 年）
    span_h: float = 500.0
    span_v: float = 625.0
    angle_deg: float = 0.0
    ice: float = 0.010        # 设计覆冰厚度 m
    kV: int = 500
    u_target: float = 0.95    # 设计控制应力比（设计裕度）
    tower_type: str = "suspension"
    gamma_G: float = 1.2
    gamma_Q: float = 1.4
    beta_z: float = 1.6       # 塔身风振系数
    mu_s: float = 1.3

    def to_dict(self):
        return asdict(self)


# ====================================================================== 荷载
def _wire(kV):
    return next(v for v in VOLTAGE_TABLE if v["kV"] == kV)


def wire_loads(model: FEModel, di: DesignInput, sc: Scenario, wind_dir_deg=90.0, v=None, ice=0.0,
               broken=False):
    """导地线挂点荷载（未乘分项系数），返回 (竖向永久向量, 风/张力可变向量)。

    坐标：x 为横担（横线路）方向，y 为顺线路方向。wind_dir_deg 为风向与线路方向夹角（90° 为横线路）。
    """
    w = _wire(sc.kV)
    v = sc.v0 if v is None else v
    w0 = v * v / 1.6
    th = math.radians(wind_dir_deg)
    X = model.X
    Fg = np.zeros(model.ndof)
    Fq = np.zeros(model.ndof)
    ang = math.radians(sc.angle_deg)
    nodes = [(n, "c") for n in di.attach_nodes] + [(n, "e") for n in di.earth_nodes]
    for k, (nd, kind) in enumerate(nodes):
        if kind == "c":
            d, wl, nsub, T, mins = w["d"], w["w"], w["n_sub"], w["T"], w["m_ins"]
        else:
            d, wl, nsub, T, mins = EARTHWIRE["d"], EARTHWIRE["w"], 1, EARTHWIRE["T"], EARTHWIRE["m_ins"]
        dd = d + 2 * ice
        wice = math.pi * ice * (d + ice) * RHO_ICE
        z = X[nd, 2]
        mz = float(TL.mu_z(z))
        alpha = 0.75 if w0 >= 300 else 0.85
        Wx = alpha * w0 * mz * 1.1 * dd * nsub * sc.span_h * math.sin(th) ** 2
        Fg[6 * nd + 2] -= G_ACC * ((wl + wice) * nsub * sc.span_v + mins)
        Fq[6 * nd + 0] += Wx
        if sc.tower_type == "tension":
            Fq[6 * nd + 0] += 2 * T * nsub * math.sin(ang / 2)   # 转角合力（指向内角侧，取 +x）
        if broken and kind == "c" and k == 0:
            fac = 0.7 if sc.tower_type == "tension" else 0.4
            Fq[6 * nd + 1] += fac * T * nsub
    return Fg, Fq


def load_cases(model: FEModel, di: DesignInput, sc: Scenario, factored=True):
    """DL/T 5486 简化荷载组合，返回 [(名称, 荷载向量)]。

    1 大风横线路 90°；2 大风 45°；3 大风顺线路 0°；4 覆冰（10 m/s 风）；5 断线（覆冰、无风）。
    """
    gG = sc.gamma_G if factored else 1.0
    gQ = sc.gamma_Q if factored else 1.0
    w0 = sc.v0 ** 2 / 1.6
    G = model.gravity_load()
    cases = []
    for name, deg, dvec in (("大风90°", 90.0, (1.0, 0.0, 0.0)), ("大风45°", 45.0, (1.0, 1.0, 0.0)),
                            ("大风0°", 0.0, (0.0, 1.0, 0.0))):
        Wt = TL.wind_static(model, w0, dvec, mu_s=sc.mu_s, beta_z=sc.beta_z)
        Fg, Fq = wire_loads(model, di, sc, deg)
        cases.append((name, gG * (G + Fg) + gQ * (Wt + Fq)))
    v_ice = 10.0
    Wt = TL.wind_static(model, v_ice ** 2 / 1.6, (1.0, 0.0, 0.0), mu_s=sc.mu_s * 1.1, beta_z=sc.beta_z)
    Fg, Fq = wire_loads(model, di, sc, 90.0, v=v_ice, ice=sc.ice)
    cases.append(("覆冰", gG * (G + Fg) + gQ * 0.9 * (Wt + Fq)))
    Fg, Fq = wire_loads(model, di, sc, 90.0, v=0.0, ice=sc.ice, broken=True)
    cases.append(("断线", gG * (G + Fg) + gQ * 0.9 * Fq))
    return cases


# ====================================================================== 杆件验算（GB 50017 / DL/T 5486 简化）
def member_capacity(cat: str, a: S.Angle, st: S.Steel, L: float):
    """返回 (受压承载力 N, 受拉承载力 N, 长细比)。单肢连接的斜/辅材计稳定强度折减 m_N。"""
    lam = L / a.iv
    phi = S.phi_b(lam, st.fy, st.E)
    mN = 1.0 if cat == "main" else min(1.0, 0.6 + 0.0015 * lam)
    Nc = phi * mN * a.A * st.f
    Nt = 0.9 * a.A * st.f
    return Nc, Nt, lam


def lam_limit(cat: str, compressed: bool = True):
    if not compressed:
        return S.LAMBDA_LIMIT["tension"]
    return S.LAMBDA_LIMIT["main" if cat == "main" else ("diagonal" if cat == "diagonal" else "auxiliary")]


def stress_ratios(g, N_env_c, N_env_t, sections=None):
    """各杆应力比（压、拉包络中较大者）。N_env_c ≥0 为最大压力，N_env_t ≥0 为最大拉力。"""
    L = g.lengths()
    secs = sections if sections is not None else g.sec
    r = np.zeros(g.n_members)
    for e in range(g.n_members):
        a = S.angle(secs[e]); st = S.steel(g.mat[e])
        Nc, Nt, _ = member_capacity(g.cat[e], a, st, L[e])
        r[e] = max(N_env_c[e] / Nc, N_env_t[e] / Nt)
    return r


# ====================================================================== 离散截面优化
def _build_model(g, extra_mass, stiff=None):
    from .model import ParamTower
    return ParamTower(g, extra_mass=extra_mass)


def analyse(pt, di, sc, sections=None, theta=None, factored=True):
    """多工况分析，返回 (压力包络, 拉力包络) 每杆 N。pt 为 model.ParamTower。"""
    fem = pt.as_femodel(sections, theta)
    cases = load_cases(fem, di, sc, factored)
    U = pt.solve_static(np.array([c[1] for c in cases]), sections, theta)
    Nall = pt.axial_forces(U, sections, theta)          # (ncase, nmem) 拉为正
    return np.maximum(-Nall, 0).max(0), np.maximum(Nall, 0).max(0)


def size_groups(g, Nc_env, Nt_env, u_target=0.95, cand=None):
    """对每个分组选最轻可行规格，返回 {group: section}。"""
    L = g.lengths()
    groups = {}
    for e, gr in enumerate(g.group):
        groups.setdefault(gr, []).append(e)
    order = cand or S.ANGLE_ORDER
    out = {}
    for gr, es in groups.items():
        cat = g.cat[es[0]]
        amin = S.angle(MIN_SECTION[cat]).A
        chosen = order[-1]
        for name in order:
            a = S.angle(name)
            if a.A < amin - 1e-12 or a.b < S.angle(MIN_SECTION[cat]).b - 1e-9:
                continue
            ok = True
            for e in es:
                st = S.steel(g.mat[e])
                Nc, Nt, lam = member_capacity(cat, a, st, L[e])
                comp = Nc_env[e] > 1.0
                if lam > lam_limit(cat, comp) or Nc_env[e] > u_target * Nc or Nt_env[e] > u_target * Nt:
                    ok = False
                    break
            if ok:
                chosen = name
                break
        out[gr] = chosen
    return out


def reverse_design(g, di: DesignInput, sc: Scenario, n_iter=6, pt=None):
    """规范逆向设计：返回 (每杆截面列表, {group: section}, 迭代信息)。"""
    from .model import ParamTower
    pt = pt or ParamTower(g, extra_mass=attach_masses(di))
    secs = list(g.sec) if all(g.sec) else ["L63x5"] * g.n_members
    hist = []
    gs = {}
    for it in range(n_iter):
        Nc, Nt = analyse(pt, di, sc, secs)
        gs_new = size_groups(g, Nc, Nt, sc.u_target)
        new = [gs_new[gr] for gr in g.group]
        changed = sum(a != b for a, b in zip(new, secs))
        hist.append(changed)
        secs, gs = new, gs_new
        if changed == 0:
            break
    return secs, gs, {"changes": hist}


def sample_scenarios(di: DesignInput, n: int, rng) -> list:
    """不可观测设计输入的情景采样：基本风速、档距、覆冰、设计裕度、电压等级（按提取置信度）、转角。"""
    rng = np.random.default_rng(rng)
    kvs = [v["kV"] for v in VOLTAGE_TABLE]
    out = []
    for _ in range(n):
        kv = di.voltage_kV
        if rng.random() > di.voltage_conf:
            i = kvs.index(kv) + rng.choice([-1, 1])
            kv = kvs[int(np.clip(i, 0, len(kvs) - 1))]
        sh = di.span_h * rng.uniform(0.8, 1.2)
        ang = di.line_angle_deg if di.tower_type == "suspension" else rng.uniform(0.0, 60.0)
        out.append(Scenario(v0=float(rng.choice([23.5, 25.0, 27.0, 29.0])), span_h=float(sh),
                            span_v=float(sh * rng.uniform(1.0, 1.5)), angle_deg=float(ang),
                            ice=float(rng.choice([0.0, 0.010, 0.015])), kV=int(kv),
                            u_target=float(rng.uniform(0.85, 1.0)), tower_type=di.tower_type))
    return out


def build_prior(g, di: DesignInput, n_scen=16, rng=0, smooth=0.12, pt=None):
    """规范逆向设计截面先验：对情景逐一做逆向设计，统计每组截面档位的离散分布（相邻档位核平滑）。

    返回 dict：groups（组名列表）、pmf（ngroup × ncat 概率矩阵，列序 = S.ANGLE_ORDER）、map（每组众数截面）、
    designs（各情景的组截面）、scenarios。
    """
    from .model import ParamTower
    pt = pt or ParamTower(g, extra_mass=attach_masses(di))
    scs = sample_scenarios(di, n_scen, rng)
    groups = sorted(set(g.group))
    gi = {gr: k for k, gr in enumerate(groups)}
    nc = len(S.ANGLE_ORDER)
    cnt = np.zeros((len(groups), nc))
    designs = []
    for sc in scs:
        _, gs, _ = reverse_design(g, di, sc, pt=pt)
        designs.append(gs)
        for gr, s in gs.items():
            cnt[gi[gr], S.ANGLE_ORDER.index(s)] += 1
    pmf = cnt / cnt.sum(1, keepdims=True)
    # 档位核平滑：向相邻 ±1、±2 档分配少量概率，容纳施工替代与设计院选材习惯
    ker = np.zeros_like(pmf)
    for sh, wgt in ((0, 1.0), (1, smooth), (-1, smooth), (2, smooth / 4), (-2, smooth / 4)):
        ker += wgt * np.roll(pmf, sh, axis=1) * (1 if sh == 0 else 1)
    # 禁止跨越最小规格的档位
    for gr, k in gi.items():
        cat = g.cat[g.group.index(gr)]
        amin = S.angle(MIN_SECTION[cat])
        for j, nm in enumerate(S.ANGLE_ORDER):
            a = S.angle(nm)
            if a.A < amin.A - 1e-12 or a.b < amin.b - 1e-9:
                ker[k, j] = 0.0
    pmf = ker / ker.sum(1, keepdims=True)
    mp = {gr: S.ANGLE_ORDER[int(np.argmax(pmf[gi[gr]]))] for gr in groups}
    return {"groups": groups, "pmf": pmf, "map": mp, "designs": designs, "scenarios": [s.to_dict() for s in scs]}
