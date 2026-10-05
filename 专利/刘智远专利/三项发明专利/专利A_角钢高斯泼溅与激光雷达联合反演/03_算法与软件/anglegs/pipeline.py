# -*- coding: utf-8 -*-
"""端到端实验：合成场景 → PTM 式基线 → 本发明联合反演（及消融）→ 置信度 → 指标与有限元对比 → 多期变化检测。"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, replace

import numpy as np

from . import _paths  # noqa: F401
from . import confidence as CF
from . import metrics as ME
from . import synth as SY
from . import topology as TP
from .baseline import PTM_SECTIONS, ptm_like
from .optimize import B_TABLE, CamData, Config, LidData, Problem, snap_widths, solve
from .raycast import build_pairs
from .surfels import generate_np, make_layout, sigmoid


@dataclass
class SceneCfg:
    preset: str = "suspension"
    seed: int = 1
    decim: float = 0.05          # 激光点频抽取比例（使塔材表面点密度与 PTM 数据量级相当）
    rings: tuple = (12.0, 26.0, 40.0, 54.0)
    radius: float = 28.0
    n_az: int = 10
    up_views: int = 8
    n_band: int = 8000
    n_bg: int = 1500
    n_ret_max: int = 160000
    n_free_max: int = 90000
    node_sigma: float = 0.055


class Scene:
    """一次合成实验所需的全部数据。"""

    def __init__(self, sc: SceneCfg, log=print, U=None, init_override=None, cams_seed_offset=0):
        t0 = time.time()
        self.sc = sc
        rng = np.random.default_rng(sc.seed)
        self.U = U if U is not None else SY.build_universe(sc.preset, seed=sc.seed)
        U = self.U
        self.geom = SY.truth_geometry(U)
        V0, b0, phi0, d10, d20, lg0 = SY.initial_state(U, rng, node_sigma=sc.node_sigma)
        self.V_noisy = V0
        self.active0 = U.in_init | U.is_cand
        # ---------- 激光雷达（保留塔体/植被回波与穿过初始模型附近的无塔体回波射线）
        lay0 = make_layout(V0, U.mi, U.mj)
        S0 = generate_np(lay0, V0, b0, phi0, d10, d20, np.where(self.active0, 3.0, -7.0))
        act_s = self.active0[lay0.sm]
        mu, ax = S0["mu"][act_s], S0["t1"][act_s]
        ha, hw = 3 * S0["s1"][act_s], 3 * S0["s2"][act_s] + 0.15

        def keep_free(o, d, tmax):
            pr = build_pairs(mu, ax, ha, hw, o, d, tmax, np.zeros(len(o)), np.full(len(o), 1.3e-3), maxk=1)
            k = (pr.end - pr.start) > 0
            return k & (rng.random(len(o)) < 0.5)
        self.lid = SY.simulate_lidar(self.geom, sc.rings, sc.radius, rng, decim=sc.decim, keep_free=keep_free)
        L = self.lid
        ret = np.flatnonzero((L.kind == 0) | (L.kind == 2))
        free = np.flatnonzero((L.kind == 1) | (L.kind == -1))
        if len(ret) > sc.n_ret_max:
            ret = np.sort(rng.choice(ret, sc.n_ret_max, replace=False))
        if len(free) > sc.n_free_max:
            free = np.sort(rng.choice(free, sc.n_free_max, replace=False))
        self.ret = LidData(L.o[ret], L.d[ret], L.rng_m[ret], L.sig_div, L.range_sigma)
        self.free = LidData(L.o[free], L.d[free], L.rng_m[free], L.sig_div, L.range_sigma)
        self.ret_kind = L.kind[ret]
        pts = L.o + L.d * np.maximum(L.rng_m, 0)[:, None]
        sel = ((L.kind == 0) | (L.kind == 2)) & (pts[:, 2] > 2.0)
        self.points = pts[sel]
        # 点密度（真值塔材表面积）
        area = float(np.sum(2 * U.b[U.exist] * np.linalg.norm(U.nodes_true[U.mj[U.exist]] - U.nodes_true[U.mi[U.exist]], axis=1)))
        n_tower = int(np.sum(L.kind == 0))
        self.lidar_stats = {"pulses_simulated": int(L.n_pulses), "tower_returns": n_tower,
                            "surface_area_m2": area, "density_pts_m2": n_tower / area,
                            "ret_rays_used": int(len(ret)), "free_rays_used": int(len(free)),
                            "veg_returns": int(np.sum(L.kind == 2)),
                            "beam_sigma_mrad": 1e3 * L.sig_div, "range_sigma_m": L.range_sigma}
        log(f"  激光：脉冲 {L.n_pulses}，塔体回波 {n_tower}（{n_tower / area:.0f} 点/m²），"
            f"用于反演 回波射线 {len(ret)}、自由空间射线 {len(free)}  {time.time() - t0:.1f}s")
        # ---------- PTM 式基线
        t1 = time.time()
        Vb, info = ptm_like(self.points, V0, U.mi, U.mj, U.in_init)
        self.V_base = Vb
        self.base_info = {k: v for k, v in info.items() if k != "owner"}
        log(f"  PTM 式基线：使用点 {info['n_points_used']}/{info['n_points']}  {time.time() - t1:.1f}s")
        # ---------- 相机（以基线节点投影抽样像素）
        t2 = time.time()
        crng = np.random.default_rng(sc.seed + 1000 + cams_seed_offset)
        self.cams, self.ext_true = SY.make_cameras(float(U.nodes_true[:, 2].max()), crng, radius=sc.radius,
                                                   rings=sc.rings, n_az=sc.n_az, up_views=sc.up_views)
        self.albedo = np.clip(crng.normal(0.55, 0.08, U.n_members), 0.3, 0.8)
        parts = {k: [] for k in ("o", "d", "dc", "v", "ci", "m", "g", "s", "val", "sk", "frac")}
        act = self.active0
        for ci, c in enumerate(self.cams):
            uv = SY.sample_pixels(c, Vb, U.mi[act], U.mj[act], b0[act], crng, n_band=sc.n_band, n_bg=sc.n_bg)
            g, mk, fr, vd, sky = SY.render_pixels(c, uv, self.geom, self.albedo, crng)
            dc = c.dcam(uv[:, 0], uv[:, 1])
            parts["o"].append(np.repeat(c.C_nom[None], len(uv), 0)); parts["d"].append(dc @ c.R_nom)
            parts["dc"].append(dc); parts["v"].append(np.repeat(c.vel[None], len(uv), 0))
            parts["ci"].append(np.full(len(uv), ci)); parts["m"].append(mk); parts["g"].append(g)
            parts["s"].append(sky); parts["val"].append(vd); parts["sk"].append(np.full(len(uv), 0.45 / c.f))
            parts["frac"].append(fr)
        cat = {k: np.concatenate(v) for k, v in parts.items()}
        self.cam = CamData(cat["o"], cat["d"], cat["dc"], cat["v"], cat["ci"].astype(np.int64),
                           np.stack([c.R_nom.T for c in self.cams]), cat["m"], cat["g"], cat["s"],
                           cat["val"], cat["sk"])
        gsd = 28.0 / self.cams[0].f
        self.cam_stats = {"views": len(self.cams), "views_up": int(sum(c.kind == "up" for c in self.cams)),
                          "image_px": [self.cams[0].W, self.cams[0].H], "f_px": self.cams[0].f,
                          "gsd_at_28m_mm": 1000 * gsd, "rays": int(self.cam.n),
                          "fg_fraction": float(np.mean(cat["frac"] > 0.5))}
        log(f"  影像：{len(self.cams)} 视图，像素射线 {self.cam.n}，28 m 处地面采样距离 {1000 * gsd:.1f} mm  "
            f"{time.time() - t2:.1f}s")
        # ---------- 初始参数（本发明以 PTM 式基线结果为初值）
        if init_override is None:
            self.init = dict(V=Vb, b=b0, phi=phi0, d1=d10, d2=d20, logit=lg0)
        else:
            self.init = init_override
        self.sym = SY.symmetry_pairs(Vb)
        self.t_build = time.time() - t0


VARIANTS = {
    "本发明": Config(label="本发明"),
    "仅激光（降级模式）": Config(label="仅激光", use_cam=False, ext=False),
    "仅影像": Config(label="仅影像", use_lidar=False),
    "圆柱基元": Config(label="圆柱基元", kind="cylinder"),
    "独立端点（不共享节点）": Config(label="独立端点", indep_ends=True, sym=False),
    "无足迹模型": Config(label="无足迹", footprint=False),
    "无负证据": Config(label="无负证据", use_free=False),
    "无对称软先验": Config(label="无对称", sym=False),
    "无外参时间标定": Config(label="无外参", ext=False),
    "无逐杆件假设检验": Config(label="无假设检验", hyp=False),
    "无朝向可观测性门控": Config(label="无门控", phi_gate=False),
    "仅激光无足迹模型": Config(label="仅激光无足迹", use_cam=False, ext=False, footprint=False),
    "仅激光无负证据": Config(label="仅激光无负证据", use_cam=False, ext=False, use_free=False),
}


def run_variant(scene: Scene, cfg: Config, log=print, stages=None, x0=None, fisher_M=0):
    U = scene.U
    t0 = time.time()
    lay = make_layout(scene.init["V"], U.mi, U.mj, kind=cfg.kind, center_xy=(0.0, 0.0))
    prob = Problem(lay, len(U.nodes_true), scene.init, scene.cam, scene.ret, scene.free, cfg, scene.sym,
                   cand_mask=U.is_cand, sun=SY.SUN)
    prob.base_nodes = list(U.g_design.meta["base_nodes"])
    prob.ref_active = U.in_init.copy()
    prob.cats = list(U.cat)
    prob.hyp_tests = getattr(cfg, "hyp", True)
    kw = {} if stages is None else {"stages": stages}
    x, hist, snaps = solve(prob, x0=x0, log=log, snap_fn=snap_widths, prune_fn=TP.prune, **kw)
    P = {k: np.asarray(v) for k, v in prob.split(x).items()}
    if cfg.indep_ends:
        E = P["E"]
        acc = np.zeros_like(P["V"]); cnt = np.zeros(len(P["V"]))
        for e in range(prob.m):
            acc[U.mi[e]] += E[e, 0]; acc[U.mj[e]] += E[e, 1]
            cnt[U.mi[e]] += 1; cnt[U.mj[e]] += 1
        P["V"] = np.where(cnt[:, None] > 0, acc / np.maximum(cnt, 1)[:, None], P["V"])
    pi = np.asarray(sigmoid(P["logit"]))
    present = pi >= 0.5
    # 规格组一致化（对称组）
    b_snap = TP.group_consistency(P["b"], U.g_design.group + [f"cand{e}" for e in range(len(U.g_design.group), prob.m)],
                                  pi)
    res = ME.evaluate_run(U, dict(V=P["V"], b=b_snap, phi=P["phi"], d1=P["d1"], d2=P["d2"], logit=P["logit"]),
                          U.sec, present, b_snap, cfg.label)
    res["ext_est"] = P["ext"].tolist()
    res["t_s"] = round(time.time() - t0, 1)
    res["topology"] = getattr(prob, "topology_log", {})
    out = {"metrics": res, "hist": hist, "P": P, "b_snap": b_snap, "present": present, "prob": prob, "x": x,
           "snaps": snaps}
    if fisher_M:
        t1 = time.time()
        G = CF.fisher_samples(prob, x, M=fisher_M, seed=7)
        nc, mc = CF.posterior_blocks(prob, x, G)
        b_cont = np.asarray(snaps.get("before_snap", x)[prob.sl["b"]])
        conf = CF.member_confidence(prob, x, nc, mc, b_cont=b_cont)
        out["conf"] = conf
        out["node_cov"] = nc
        out["mem_cov"] = mc
        out["b_cont"] = b_cont
        out["t_fisher"] = round(time.time() - t1, 1)
    return out


def ptm_metrics(scene: Scene):
    U = scene.U
    b = np.array([0.22 if c == "main" else 0.14 if c == "diagonal" else 0.09 for c in U.cat])
    present = U.in_init.copy()
    r = ME.evaluate_run(U, dict(V=scene.V_base, b=b, phi=scene.init["phi"], d1=np.zeros(U.n_members),
                                d2=np.zeros(U.n_members), logit=np.where(present, 7.0, -7.0)),
                        U.sec, present, b, "PTM 式基线")
    r0 = ME.evaluate_run(U, dict(V=scene.V_noisy, b=b, phi=scene.init["phi"], d1=np.zeros(U.n_members),
                                 d2=np.zeros(U.n_members), logit=np.where(present, 7.0, -7.0)),
                         U.sec, present, b, "初始（PTM 定位误差）")
    return r, r0


def fe_compare(scene: Scene, runs: dict):
    """真值 / PTM 统一截面 / 各方法 的有限元响应对比。"""
    U = scene.U
    out = {}
    gt = ME.build_graph(U, U.nodes_true, U.exist, U.sec)
    out["真值"] = ME.fe_response(gt)
    ptm_secs = [PTM_SECTIONS[c] for c in U.cat]
    out["PTM 式基线"] = ME.fe_response(ME.build_graph(U, scene.V_base, U.in_init, ptm_secs))
    for name, r in runs.items():
        secs = [ME.section_name_for_width(b) for b in r["b_snap"]]
        out[name] = ME.fe_response(ME.build_graph(U, r["P"]["V"], r["present"], secs))
    tv = out["真值"]
    for k, v in out.items():
        v["tip_err_rel"] = abs(v["tip_disp_m"] - tv["tip_disp_m"]) / tv["tip_disp_m"]
        v["freq_err_rel_max"] = float(np.max(np.abs(np.array(v["freq_Hz"]) - np.array(tv["freq_Hz"])) / np.array(tv["freq_Hz"])))
    return out


def calibration(scene: Scene, run: dict, kappa_ext=None, kb_ext=None):
    """置信度校准：节点误差与预测标准差的秩相关、马氏距离覆盖率；存在概率可靠性。
    kappa_ext / kb_ext：在另一场景（标定场景）上求得的协方差膨胀系数，用于检验其在新场景上的覆盖率（外推校准）。"""
    out = _calibration(scene, run)
    if kappa_ext is not None:
        U = scene.U
        V = run["P"]["V"]
        err = V - U.nodes_true
        used = np.zeros(len(V), bool)
        used[U.mi[U.exist]] = True; used[U.mj[U.exist]] = True
        z2 = np.array([e @ np.linalg.solve(C, e) for e, C in zip(err, run["node_cov"])])[used]
        out["kappa_ext"] = float(kappa_ext)
        out["coverage95_ext"] = float(np.mean(z2 / kappa_ext ** 2 < 7.815))
    if kb_ext is not None:
        U = scene.U
        ex = U.exist & run["present"]
        bz = (run["b_cont"][ex] - U.b[ex]) / np.maximum(run["conf"]["sig_b"][ex], 1e-6)
        out["width_kappa_ext"] = float(kb_ext)
        out["width_coverage95_ext"] = float(np.mean(np.abs(bz) / kb_ext < 1.96))
    return out


def _calibration(scene: Scene, run: dict):
    U = scene.U
    V = run["P"]["V"]
    err = V - U.nodes_true
    used = np.zeros(len(V), bool)
    used[U.mi[U.exist]] = True; used[U.mj[U.exist]] = True
    nc = run["node_cov"]
    z2 = np.array([e @ np.linalg.solve(C, e) for e, C in zip(err, nc)])[used]
    sig = run["conf"]["sig_v"][used]
    en = np.linalg.norm(err, axis=1)[used]
    from scipy.stats import spearmanr
    kappa = float(np.sqrt(np.median(z2) / 2.366))         # χ²(3) 中位数 2.366
    out = {"spearman_sigma_vs_err": float(spearmanr(sig, en).correlation),
           "coverage95_raw": float(np.mean(z2 < 7.815)), "kappa": kappa,
           "coverage95_scaled": float(np.mean(z2 / kappa ** 2 < 7.815))}
    # 杆件肢宽
    ex = U.exist & run["present"]
    bz = (run["b_cont"][ex] - U.b[ex]) / np.maximum(run["conf"]["sig_b"][ex], 1e-6)
    out["width_coverage95_raw"] = float(np.mean(np.abs(bz) < 1.96))
    kb = float(np.median(np.abs(bz)) / 0.6745)
    out["width_kappa"] = kb
    out["width_coverage95_scaled"] = float(np.mean(np.abs(bz) / kb < 1.96))
    # 规格后验
    post = CF.spec_posterior(run["b_cont"], run["conf"]["sig_b"] * kb, B_TABLE)
    it = np.argmin(np.abs(U.b[:, None] - B_TABLE[None]), 1)
    p_true = post[np.arange(len(it)), it]
    out["spec_top1_prob_mean"] = float(np.mean(post.max(1)[ex]))
    out["spec_true_prob_mean"] = float(np.mean(p_true[ex]))
    # 低置信杆件是否对应大误差
    c = run["conf"]["c"]
    werr = np.abs(run["b_snap"] - U.b)
    lo = ex & (c < np.percentile(c[ex], 20))
    hi = ex & (c > np.percentile(c[ex], 80))
    out["width_err_low_conf_mm"] = float(1000 * np.mean(werr[lo]))
    out["width_err_high_conf_mm"] = float(1000 * np.mean(werr[hi]))
    # 存在概率分箱可靠性（ECE）
    pi = run["conf"]["pi"]
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for a, b in zip(bins[:-1], bins[1:]):
        m = (pi >= a) & (pi < b if b < 1 else pi <= b)
        if m.any():
            ece += m.mean() * abs(pi[m].mean() - U.exist[m].mean())
    out["exist_ECE"] = float(ece)
    return out


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o
