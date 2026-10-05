# -*- coding: utf-8 -*-
"""端到端仿真：初始双倾角航线 → 置信度 → 四种补测方法 → 指标。"""
from __future__ import annotations

import time

import numpy as np

from . import confidence as C
from . import planner as PL
from . import viewpoints as VP
from ._tk import lidar as L
from .evaluate import fe_response, metrics
from .safety import SafetyShell, resample, tower_samples
from .scenario import initial_flight, make_scenario, mirror_maps
from .sensitivity import importance_weights

SPEED = 4.0          # 补测飞行速度 m/s
DWELL = 4.0          # 每视点悬停驻留 s
DECIM = 0.25         # 扫描抽稀（加速，评估时折算回全点频）
K_ROUND = 8          # 每轮补测视点数
HOME = np.array([22.0, -22.0, 6.0])


class Context:
    """一次场景的公共数据（几何、安全壳、候选视点、权重、初始观测）。"""

    def __init__(self, variant="standard", seed=0, kv=220.0, sigma_pos=0.5, scanner=None, verbose=True):
        t0 = time.time()
        self.sc = make_scenario(variant, seed=seed, voltage_kv=kv)
        self.scanner = scanner or L.Scanner()
        self.maps_n, self.maps_e = mirror_maps(self.sc.prior)
        self.shell = SafetyShell(self.sc.live, kv=kv, sigma_pos=sigma_pos, tower_pts=tower_samples(self.sc.prior),
                                 grounded=self.sc.grounded)
        self.w, self.sens = importance_weights(self.sc.prior)
        self.fe_gt = fe_response(self.sc.gt)
        P, self.rejected = VP.generate(self.sc, self.shell)
        yaw, pitch = VP.aim(P)
        self.cand = VP.predict(self.sc.geom_plan, self.sc.prior, P, yaw, pitch, self.scanner, dwell=DWELL)
        # 安全图：候选 + HOME + 初始航线终点
        tr, mounts = initial_flight(self.sc)
        self.init_tr, self.init_mounts = tr, mounts
        self.p_init_end = tr.pos[-1]
        extra = [HOME, self.p_init_end]
        H = self.sc.meta["H"]
        # 转场通道：初始航线终点 → 塔顶上方候选点；HOME → 最近低空候选点（等距插点）
        tgt = self.cand.pos[np.argmin(np.linalg.norm(self.cand.pos - self.p_init_end, axis=1))]
        for s in np.linspace(0, 1, int(np.linalg.norm(tgt - self.p_init_end) / 6) + 2)[1:-1]:
            extra.append(self.p_init_end + s * (tgt - self.p_init_end))
        tgt = self.cand.pos[np.argmin(np.linalg.norm(self.cand.pos - HOME, axis=1))]
        for s in np.linspace(0, 1, int(np.linalg.norm(tgt - HOME) / 6) + 2)[1:-1]:
            extra.append(HOME + s * (tgt - HOME))
        self.nodes = np.vstack([self.cand.pos, np.asarray(extra, float)])
        self.i_home = len(self.cand.pos); self.i_start = self.i_home + 1
        self.D, self.pred = PL.safe_graph(self.nodes, self.shell, r_conn=12.0)
        self.L = C.member_frames(self.sc.prior.nodes, np.asarray(self.sc.prior.mi), np.asarray(self.sc.prior.mj))[3]
        self.init_ev = self._initial_evidence()
        self.t_setup = time.time() - t0
        if verbose:
            print(f"[{variant}] 候选 {len(P)}（壳内剔除 {len(self.rejected)}），壳半径 {self.shell.radius:.2f} m，"
                  f"准备 {self.t_setup:.1f} s")

    def _initial_evidence(self):
        ev = C.Evidence(self.sc.prior.n_members)
        for k, m in enumerate(self.init_mounts):
            c = L.scan(self.sc.geom_gt, self.init_tr, self.scanner, m, seed=100 + k, decim=DECIM)
            cp = L.scan(self.sc.geom_plan, self.init_tr, self.scanner, m, seed=100 + k, decim=DECIM)
            exp = np.bincount(cp["member"][cp["member"] >= 0], minlength=self.sc.prior.n_members) / DECIM
            ev.add_cloud(c["xyz"], c["origin"], exp)
        return ev

    def copy_ev(self, ev):
        e2 = C.Evidence(ev.n_members)
        e2.xyz = list(ev.xyz); e2.origin = list(ev.origin); e2.expected = ev.expected.copy()
        return e2

    def confidence(self, ev):
        return C.compute_confidence(ev, self.sc.prior, self.maps_n, self.maps_e, decim=DECIM)


def _scan_hover(ctx, ev, v, seed):
    cd = ctx.cand
    c = VP.hover_scan(ctx.sc.geom_gt, cd.pos[v], cd.yaw[v], cd.pitch[v], ctx.scanner, DWELL, seed, DECIM)
    cp = VP.hover_scan(ctx.sc.geom_plan, cd.pos[v], cd.yaw[v], cd.pitch[v], ctx.scanner, DWELL, seed, DECIM)
    exp = np.bincount(cp["member"][cp["member"] >= 0], minlength=ctx.sc.prior.n_members) / DECIM
    ev.add_cloud(c["xyz"], c["origin"], exp)
    return len(c["xyz"]) / DECIM, len(cp["xyz"]) / DECIM


def transit(ctx, a, b):
    """a→b 直线若安全则直飞，否则经安全图最近节点最短路绕行。返回中间点列表（不含 a、b）。"""
    if ctx.shell.segment_safe(a, b):
        return []
    ia = int(np.argmin(np.linalg.norm(ctx.nodes - a, axis=1)))
    ib = int(np.argmin(np.linalg.norm(ctx.nodes - b, axis=1)))
    p = PL.path_from_pred(ctx.pred, ia, ib) or []
    return [ctx.nodes[k] for k in p]


def run_none(ctx):
    res = ctx.confidence(ctx.init_ev)
    m = metrics(ctx.sc, res, ctx.fe_gt, ctx.w)
    m.update({"path_m": 0.0, "time_s": 0.0, "n_views": 0,
              "violations": ctx.shell.violations(ctx.init_tr.pos)["segments"]})
    return {"res": res, "metrics": m, "path": np.zeros((0, 3)), "views": []}


def run_uniform(ctx, radius=13.0, n_rings=None, pitch=-8.0):
    """均匀加密环绕：在带电安全壳允许的高度上布置等间距环（自动跳过与壳相交的环），返回同时统计
    “不考虑安全壳的全高度等距环绕”的违规次数作对照。"""
    H = ctx.sc.meta["H"]
    zs_all = np.arange(4.0, H + 4.1, 5.0)
    ev = ctx.copy_ev(ctx.init_ev)
    paths, rings, naive = [], [], []
    for z in zs_all:
        tr = L.orbit_path([0, 0], radius, z, speed=SPEED)
        naive.append(tr.pos)
        if not ctx.shell.is_safe(resample(tr.pos, 0.5)).all():
            continue
        rings.append(z)
        paths.append(tr)
    m_or = L.Mount(yaw=90, pitch=pitch, lever=(0, 0, 0))
    for k, tr in enumerate(paths):
        c = L.scan(ctx.sc.geom_gt, tr, ctx.scanner, m_or, seed=500 + k, decim=DECIM)
        cp = L.scan(ctx.sc.geom_plan, tr, ctx.scanner, m_or, seed=500 + k, decim=DECIM)
        exp = np.bincount(cp["member"][cp["member"] >= 0], minlength=ctx.sc.prior.n_members) / DECIM
        ev.add_cloud(c["xyz"], c["origin"], exp)
    # 航迹：起点 → 各环（环间垂直爬升，同一方位角）→ HOME；环间转场经安全图
    pts = [ctx.p_init_end]
    for tr in paths:
        ring = list(tr.pos[::10])
        pts += transit(ctx, pts[-1], ring[0]) + ring
    pts += transit(ctx, pts[-1], HOME) + [HOME]
    pts = np.asarray(pts)
    length = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    res = ctx.confidence(ev)
    m = metrics(ctx.sc, res, ctx.fe_gt, ctx.w)
    naive_path = np.concatenate(naive)
    m.update({"path_m": length, "time_s": length / SPEED, "n_views": len(rings), "rings_z": [float(z) for z in rings],
              "violations": ctx.shell.violations(pts)["segments"],
              "violations_naive_full_height": ctx.shell.violations(naive_path)["segments"]})
    return {"res": res, "metrics": m, "path": pts, "views": rings}


def run_nbv(ctx, use_sensitivity=True, stop=None, verbose=True, force_rounds=None):
    """迭代式补测：每轮 置信度 → 加权增益贪心选 K 点 → 安全图 TSP → 飞行采集 → 增量更新；按停止判据结束。"""
    w = ctx.w if use_sensitivity else np.ones_like(ctx.w)
    stop = stop or PL.StopRule()
    ev = ctx.copy_ev(ctx.init_ev)
    res = ctx.confidence(ev)
    used, full_route, t_used, length = [], [ctx.i_start], 0.0, 0.0
    cur = ctx.i_start
    hit_frac = 0.6
    hist = []
    reason = None
    realized = predicted = 0.0
    rnd = 0
    while True:
        deficit = float(np.sum(w * (1 - res.c)) / np.sum(w))
        cf = res.counts / DECIM
        bf = res.bins / DECIM
        st = PL.PlanState(cf, bf, res.c, w, ctx.L, hit_frac)
        V = len(ctx.cand.pos)
        unreach = ~np.isfinite(ctx.D[ctx.i_start, :V]) | ~np.isfinite(ctx.D[ctx.i_home, :V])  # 安全图不可达视点
        sel, gains, costs = PL.lazy_greedy(st, ctx.cand, K_ROUND, ctx.D, cur, SPEED, used, exclude_mask=unreach)
        best_rate = (sum(gains) / sum(costs) / np.sum(w)) if sel else 0.0
        hist.append({"round": rnd, "deficit": deficit, "best_rate": best_rate, "t": t_used, "path": length,
                     "n_low": int((res.c < 0.5).sum()), "realized": realized, "predicted": predicted})
        if force_rounds is None:
            reason = stop.check(deficit, best_rate, realized, predicted, t_used, rnd)
        else:
            reason = "固定轮次" if rnd >= force_rounds or not sel else None
        if reason or not sel:
            reason = reason or "无可选视点"
            break
        route = PL.tsp_route(ctx.D, cur, sel)
        predicted = float(sum(gains))
        c_before = res.c.copy()
        obs = pred = 0.0
        for v in route[1:]:
            o, p = _scan_hover(ctx, ev, v, seed=1000 + v)
            obs += o; pred += p
        res = ctx.confidence(ev)
        realized = float(np.sum(w * np.maximum(0, res.c - c_before)))
        # 预测/实测比自适应修正期望点数折减
        if predicted > 0:
            hit_frac = float(np.clip(hit_frac * (0.5 + 0.5 * min(2.0, realized / predicted)), 0.2, 1.0))
        seg_len = PL.route_length(route, ctx.D)
        length += seg_len
        t_used += seg_len / SPEED + DWELL * len(sel)
        used += sel
        full_route += route[1:]
        cur = route[-1]
        rnd += 1
        if verbose:
            print(f"  轮 {rnd}: 选 {len(sel)} 点，缺口 {deficit:.3f}，预测增益 {predicted:.2f}，实测 {realized:.2f}，"
                  f"累计 {length:.0f} m / {t_used:.0f} s")
    back = ctx.D[cur, ctx.i_home]
    full_route.append(ctx.i_home)
    length += back; t_used += back / SPEED
    path = PL.expand_route(full_route, ctx.pred, ctx.nodes)
    m = metrics(ctx.sc, res, ctx.fe_gt, ctx.w)
    m.update({"path_m": float(length), "time_s": float(t_used), "n_views": len(used), "rounds": rnd,
              "stop_reason": reason, "violations": ctx.shell.violations(path)["segments"],
              "min_live_dist": ctx.shell.violations(path)["min_live_dist"],
              "views_inside_shell": int((~ctx.shell.is_safe(ctx.cand.pos[used])).sum()) if used else 0})
    return {"res": res, "metrics": m, "path": path, "views": used, "history": hist}
