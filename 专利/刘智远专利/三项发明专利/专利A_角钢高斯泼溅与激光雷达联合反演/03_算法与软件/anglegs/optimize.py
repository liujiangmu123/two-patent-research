# -*- coding: utf-8 -*-
"""联合目标函数与分阶段优化（梯度只回传桁架参数）。

参数向量 x = [V(n×3), b(m), φ(m), δ1(m), δ2(m), logit(m), app(2m), ext(7)]（独立端点消融另加 Vend(m×2×3)）。
目标函数（每射线负对数似然之和 + 先验，按射线总数归一化）：
    相机：轮廓 BCE + 灰度 Huber；激光：混合距离似然 + 回波前方自由空间；无塔体回波射线：自由空间负证据；
    先验：节点/截面/偏心弱先验、鲁棒对称（Geman–McClure）、规格软吸附、存在稀疏。
冻结通过 L-BFGS-B 的上下界相等实现；配对在每个外循环按当前参数重建。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

import autograd.numpy as anp
import numpy as np
from autograd import grad, value_and_grad
from scipy.optimize import minimize

from . import _paths  # noqa: F401
from towerkit import sections as TS

from . import fused as FU
from .raycast import Pairs, build_pairs
from .render import camera_terms, lidar_free_terms, lidar_return_terms, pair_response, ray_basis
from .surfels import Layout, cross, generate, generate_np, sigmoid

B_TABLE = np.array(sorted({a.b for a in TS.ANGLES.values()}))


# ====================================================================== 数据容器
@dataclass
class CamData:
    o0: np.ndarray
    d0: np.ndarray
    dcam: np.ndarray
    vel: np.ndarray
    cam: np.ndarray
    Rt: np.ndarray           # (ncam,3,3) 记录姿态的转置（相机→世界）
    mask: np.ndarray
    gray: np.ndarray
    sky: np.ndarray
    valid: np.ndarray
    sigk: np.ndarray         # 像素足迹（rad）：0.45 px / f
    e1: np.ndarray = None
    e2: np.ndarray = None

    def __post_init__(self):
        self.e1, self.e2 = ray_basis(self.d0)

    @property
    def n(self):
        return len(self.o0)


@dataclass
class LidData:
    o: np.ndarray
    d: np.ndarray
    dmeas: np.ndarray        # 回波距离；自由空间射线为地面回波距离或 −1（无回波）
    sig_div: float
    sigr: float
    e1: np.ndarray = None
    e2: np.ndarray = None

    def __post_init__(self):
        self.e1, self.e2 = ray_basis(self.d)

    @property
    def n(self):
        return len(self.o)


@dataclass
class Config:
    use_cam: bool = True
    use_lidar: bool = True
    use_free: bool = True
    footprint: bool = True
    sym: bool = True
    ext: bool = True
    indep_ends: bool = False
    kind: str = "angle"
    w_cam: float = 1.0
    w_ret: float = 1.0
    w_free: float = 0.3
    w_photo: float = 0.5
    lam_sym: float = 30.0
    c_sym: float = 0.03
    lam_spec: float = 2.0
    tau_spec: float = 0.0025
    lam_sparse: float = 0.5
    sig_node: float = 0.25
    sig_b: float = 0.06
    sig_delta: float = 0.06
    sig_phi: float = 0.15          # 连续朝向先验（rad）；90°/180° 翻转由逐杆件假设检验处理
    sig_app: float = 0.5
    sig_ext: tuple = (0.01, 0.01, 0.01, 0.05, 0.05, 0.05, 0.02)
    p_det: float = 0.8
    maxk: int = 48
    margin: float = 0.06
    prune: float = 0.10
    hyp: bool = True
    phi_gate: bool = True          # 朝向可观测性门控：肢宽 < 63 mm 或杆长 < 2.5 m 的杆件朝向保持设计先验，不做连续更新
    iter_mult: float = 1.0
    label: str = "本发明"


# ====================================================================== 问题
class Problem:
    def __init__(self, lay: Layout, n_nodes, init: dict, cam: CamData | None, ret: LidData | None,
                 free: LidData | None, cfg: Config, sym_pairs=(), cand_mask=None, sun=None):
        self.lay, self.cfg = lay, cfg
        self.n, self.m = n_nodes, lay.n_members
        self.cam = cam if cfg.use_cam else None
        self.ret = ret if cfg.use_lidar else None
        self.free = free if (cfg.use_lidar and cfg.use_free) else None
        self.init = {k: np.asarray(v, float).copy() for k, v in init.items()}
        self.sym = list(sym_pairs) if cfg.sym else []
        self.cand = np.zeros(self.m, bool) if cand_mask is None else np.asarray(cand_mask, bool)
        # app：每杆反照率；ext：相机视轴安装误差 ω(3)、杠杆臂(3)、曝光时间偏移(1)、环境光与漫反射系数(2)
        sizes = [("V", 3 * self.n), ("b", self.m), ("phi", self.m), ("d1", self.m), ("d2", self.m),
                 ("logit", self.m), ("app", self.m), ("ext", 9)]
        if cfg.indep_ends:
            sizes.append(("E", 6 * self.m))
        self.sl, o = {}, 0
        for k, s in sizes:
            self.sl[k] = slice(o, o + s); o += s
        self.size = o
        # 变量尺度（优化在无量纲变量 z=x/scale 上进行，改善 L-BFGS 条件数）
        sc = {"V": 0.05, "b": 0.01, "phi": 0.3, "d1": 0.01, "d2": 0.01, "logit": 1.0, "app": 0.1, "E": 0.05}
        self.scale = np.ones(self.size)
        for k, s in self.sl.items():
            if k == "ext":
                self.scale[s] = [1e-3, 1e-3, 1e-3, 1e-2, 1e-2, 1e-2, 1e-3, 0.1, 0.1]
            else:
                self.scale[s] = sc[k]
        self.base_nodes = []
        self.ref_active = None
        self.app_idx = lay.sm.astype(np.int64)
        self.sun = np.asarray(sun if sun is not None else (0.45, -0.55, 0.70), float)
        self.sun = self.sun / np.linalg.norm(self.sun)
        self.pairs = {}
        self.N = max(1, (self.cam.n if self.cam is not None else 0) + (self.ret.n if self.ret is not None else 0)
                     + (self.free.n if self.free is not None else 0))
        if self.sym:
            self.sym_i = np.array([p[0] for p in self.sym]); self.sym_j = np.array([p[1] for p in self.sym])
            self.sym_M = np.stack([p[2] for p in self.sym])

    # ------------------------------------------------------------------ 打包
    def pack(self, P: dict) -> np.ndarray:
        x = np.zeros(self.size)
        for k, s in self.sl.items():
            x[s] = np.asarray(P[k], float).ravel()
        return x

    def split(self, x):
        P = {}
        for k, s in self.sl.items():
            P[k] = x[s]
        P["V"] = anp.reshape(P["V"], (self.n, 3))
        if "E" in P:
            P["E"] = anp.reshape(P["E"], (self.m, 2, 3))
        return P

    def x0(self):
        P = dict(self.init)
        P.setdefault("app", np.full(self.m, 0.5))
        P.setdefault("ext", np.array([0, 0, 0, 0, 0, 0, 0, 0.35, 0.6]))
        if self.cfg.indep_ends:
            V = P["V"]
            P["E"] = np.stack([V[self.lay.mi], V[self.lay.mj]], 1)
        return self.pack(P)

    # ------------------------------------------------------------------ 几何
    def surfels(self, P):
        return generate(self.lay, P["V"], P["b"], P["phi"], P["d1"], P["d2"], P["logit"],
                        P.get("E") if self.cfg.indep_ends else None)

    def cam_rays(self, P):
        c = self.cam
        ext = P["ext"]
        w = ext[0:3]
        cr = anp.stack([w[1] * c.dcam[:, 2] - w[2] * c.dcam[:, 1],
                        w[2] * c.dcam[:, 0] - w[0] * c.dcam[:, 2],
                        w[0] * c.dcam[:, 1] - w[1] * c.dcam[:, 0]], 1)
        Rt = c.Rt[c.cam]
        dd = c.d0 + anp.einsum("rij,rj->ri", Rt, cr)
        dd = dd / anp.sqrt(anp.sum(dd * dd, 1))[:, None]
        o = c.o0 + ext[3:6][None, :] + c.vel * ext[6]
        return o, dd

    # ------------------------------------------------------------------ 配对
    def repair(self, x):
        P = {k: np.asarray(v) for k, v in self.split(x).items()}
        S = generate_np(self.lay, P["V"], P["b"], P["phi"], P["d1"], P["d2"], P["logit"],
                        P.get("E") if self.cfg.indep_ends else None)
        smax = np.maximum(S["s1"], S["s2"])
        ha = 3.0 * S["s1"]
        hw = 3.0 * S["s2"] + self.cfg.margin
        self._smax = smax
        cfg = self.cfg
        self.K = {}
        if self.cam is not None:
            o, d = (np.asarray(a) for a in self.cam_rays(P))
            pr = build_pairs(S["mu"], S["t1"], ha, hw, o, d, np.full(self.cam.n, 400.0), np.zeros(self.cam.n),
                             self.cam.sigk, maxk=cfg.maxk)
            self.pairs["cam"] = (pr, 3.0 * smax[pr.ps])
            rc = FU.RayConst(pr, self.cam.e1, self.cam.e2, np.zeros(self.cam.n), self.cam.sigk, 3.0 * smax[pr.ps])
            self.K["cam"] = FU.CamConst(rc, self.cam.mask, self.cam.gray, self.cam.sky, self.cam.valid, cfg.w_photo)
            # 可见面法向符号（面元法向与视线异侧为可见面），配对时固定
            nrm = np.cross(S["t1"], S["t2"])
            self.cam_vis_sign = -np.sign(np.sum(nrm[pr.ps] * d[pr.pr], 1))
        for key, Ld in (("ret", self.ret), ("free", self.free)):
            if Ld is None:
                continue
            if key == "ret":
                tmax = Ld.dmeas + 0.35
            else:
                tmax = np.where(Ld.dmeas > 0, Ld.dmeas - 0.3, 300.0)
            sk = np.full(Ld.n, Ld.sig_div if cfg.footprint else 0.0)
            pr = build_pairs(S["mu"], S["t1"], ha, hw, Ld.o, Ld.d, tmax, np.zeros(Ld.n), sk, maxk=cfg.maxk)
            extra = 3.0 * smax[pr.ps]
            rc = FU.RayConst(pr, Ld.e1, Ld.e2, np.zeros(Ld.n), np.full(Ld.n, Ld.sig_div), extra,
                             footprint=cfg.footprint)
            if key == "ret":
                front = (pr.tc < Ld.dmeas[pr.pr] - 3.0 * Ld.sigr - 0.05).astype(float)
                self.pairs[key] = (pr, extra, front)
                self.K[key] = FU.RetConst(rc, Ld.dmeas, Ld.sigr, front, cfg.w_ret, cfg.w_free if cfg.use_free else 0.0)
            else:
                self.pairs[key] = (pr, extra)
                self.K[key] = FU.FreeConst(rc, (Ld.dmeas > 0).astype(float), cfg.w_free, cfg.p_det)
        return {k: v[0].n for k, v in self.pairs.items()}

    def set_blur(self, blur):
        for k in self.K.values():
            (k.rc if hasattr(k, "rc") else k).blur = float(blur)

    # ------------------------------------------------------------------ 损失
    def _data_terms(self, P, blur):
        """融合算子实现（numba 前向 + 解析反向）。"""
        S = self.surfels(P)
        self.set_blur(blur)
        args = (S["mu"], S["t1"], S["t2"], S["s1"], S["s2"], S["alpha"])
        out = []
        cfg = self.cfg
        if self.cam is not None:
            o, d = self.cam_rays(P)
            H = FU.response(*args, o, d, self.K["cam"].rc)
            out.append(cfg.w_cam * FU.cam_loss(H, self.pair_colors(S, P), self.K["cam"]))
        if self.ret is not None:
            H = FU.response(*args, self.ret.o, self.ret.d, self.K["ret"].rc)
            out.append(FU.ret_loss(H, self.K["ret"]))
        if self.free is not None:
            H = FU.response(*args, self.free.o, self.free.d, self.K["free"].rc)
            out.append(FU.free_loss(H, self.K["free"]))
        return out

    def pair_colors(self, S, P):
        """逐配对颜色 = 杆件反照率 ×（环境光 + 漫反射·max(0, 可见面法向·太阳方向)）（autograd 可微）。"""
        from .adops import take
        pr = self.pairs["cam"][0]
        nrm = cross(S["t1"], S["t2"])
        lam = anp.maximum(0.0, self.cam_vis_sign * anp.sum(take(nrm, pr.ps) * self.sun[None, :], 1))
        ext = P["ext"]
        return take(P["app"], self.app_idx[pr.ps]) * (ext[7] + ext[8] * lam)

    def _data_terms_ref(self, P, blur):
        """autograd 参考实现（与融合算子数学等价，用于测试梯度一致性）。"""
        S = self.surfels(P)
        out = []
        cfg = self.cfg
        if self.cam is not None:
            pr, lim = self.pairs["cam"]
            o, d = self.cam_rays(P)
            h, tk = pair_response(S, pr.pr, pr.ps, o, d, self.cam.e1, self.cam.e2, np.zeros(self.cam.n),
                                  self.cam.sigk, lim, extra_blur=blur, footprint=True)
            out.append(cfg.w_cam * camera_terms(h, tk, pr, self.cam.mask, self.cam.gray, self.cam.sky,
                                                self.pair_colors(S, P), self.cam.valid.astype(float), cfg.w_photo))
        if self.ret is not None:
            pr, lim, front = self.pairs["ret"]
            L = self.ret
            sk = np.full(L.n, L.sig_div)
            h, tk = pair_response(S, pr.pr, pr.ps, L.o, L.d, L.e1, L.e2, np.zeros(L.n), sk, lim, extra_blur=blur,
                                  footprint=cfg.footprint)
            nll, fr = lidar_return_terms(h, tk, pr, L.dmeas, L.sigr, front)
            out.append(cfg.w_ret * nll + (cfg.w_free * fr if cfg.use_free else 0.0 * fr))
        if self.free is not None:
            pr, lim = self.pairs["free"]
            L = self.free
            sk = np.full(L.n, L.sig_div)
            h, tk = pair_response(S, pr.pr, pr.ps, L.o, L.d, L.e1, L.e2, np.zeros(L.n), sk, lim, extra_blur=blur,
                                  footprint=cfg.footprint)
            fs = lidar_free_terms(h, pr)                       # = −log T
            ground = (L.dmeas > 0).astype(float)
            T = anp.exp(-fs)
            dropout = -anp.log((1 - cfg.p_det) + cfg.p_det * T)
            out.append(cfg.w_free * (ground * fs + (1 - ground) * dropout))
        return out

    def per_ray(self, x, blur=0.0):
        P = self.split(x)
        return anp.concatenate(self._data_terms(P, blur))

    def objective_ref(self, x, blur=0.0):
        """autograd 参考实现的目标函数（测试用）。"""
        P = self.split(x)
        tot = 0.0
        for t in self._data_terms_ref(P, blur):
            tot = tot + anp.sum(t)
        return (tot + self.prior(P)) / self.N

    def prior(self, P):
        cfg = self.cfg
        I = self.init
        val = anp.sum((P["V"] - I["V"]) ** 2) / (2 * cfg.sig_node ** 2)
        val = val + anp.sum((P["b"] - I["b"]) ** 2) / (2 * cfg.sig_b ** 2)
        val = val + (anp.sum(P["d1"] ** 2) + anp.sum(P["d2"] ** 2)) / (2 * cfg.sig_delta ** 2)
        val = val + anp.sum((P["phi"] - I["phi"]) ** 2) / (2 * cfg.sig_phi ** 2)
        val = val + anp.sum((P["app"] - 0.5) ** 2) / (2 * cfg.sig_app ** 2)
        val = val + anp.sum((P["ext"][:7] / np.asarray(cfg.sig_ext)) ** 2) / 2
        val = val + ((P["ext"][7] - 0.35) ** 2 + (P["ext"][8] - 0.6) ** 2) / (2 * 0.3 ** 2)
        if self.cfg.indep_ends:
            Ei = np.stack([I["V"][self.lay.mi], I["V"][self.lay.mj]], 1)
            val = val + anp.sum((P["E"] - Ei) ** 2) / (2 * cfg.sig_node ** 2)
        if self.sym:
            Vi = P["V"][self.sym_i]
            Vj = anp.einsum("pab,pb->pa", self.sym_M, P["V"][self.sym_j])
            r2 = anp.sum((Vi - Vj) ** 2, 1)
            val = val + cfg.lam_sym * anp.sum(r2 / (r2 + cfg.c_sym ** 2))
        pi = sigmoid(P["logit"])
        val = val + cfg.lam_sparse * anp.sum(pi)
        if self._spec_on:
            # 规格软吸附：对规格表的软最小距离（log-sum-exp，平移量取常数以保证数值稳定，不影响梯度）
            bv = np.asarray(getattr(P["b"], "_value", P["b"]), float)
            mn = np.min((bv[:, None] - B_TABLE[None, :]) ** 2, 1) / (2 * cfg.tau_spec ** 2)
            dd = (P["b"][:, None] - B_TABLE[None, :]) ** 2 / (2 * cfg.tau_spec ** 2)
            val = val + cfg.lam_spec * anp.sum(-anp.log(anp.sum(anp.exp(-(dd - mn[:, None])), 1)) + mn)
        return val

    _spec_on = False

    def objective(self, x, blur=0.0):
        P = self.split(x)
        terms = self._data_terms(P, blur)
        tot = 0.0
        for t in terms:
            tot = tot + anp.sum(t)
        return (tot + self.prior(P)) / self.N

    # ------------------------------------------------------------------ 冻结与边界
    def bounds(self, x, free_blocks, frozen_members=None):
        lb, ub = x.copy(), x.copy()
        for k in free_blocks:
            if k not in self.sl:
                continue
            s = self.sl[k]
            if k == "b":
                lb[s], ub[s] = 0.040, 0.26       # GB/T 706 最小肢宽 40 mm
            elif k == "logit":
                lb[s], ub[s] = -7.0, 7.0
            elif k in ("d1", "d2"):
                lb[s], ub[s] = -0.12, 0.12
            elif k == "app":
                lb[s], ub[s] = 0.0, 1.2
            elif k == "ext":
                lb[s] = [-0.2] * 7 + [0.0, 0.0]
                ub[s] = [0.2] * 7 + [1.5, 1.5]
            else:
                lb[s], ub[s] = -np.inf, np.inf
        if frozen_members is not None and len(frozen_members):
            fm = np.asarray(frozen_members)
            for k in ("b", "phi", "d1", "d2", "logit"):
                s = self.sl[k]
                idx = np.arange(s.start, s.stop)[fm]
                lb[idx] = x[idx]; ub[idx] = x[idx]
        if self.cfg.phi_gate and "phi" in free_blocks and "phi" in self.sl:
            # 朝向可观测性门控（与逐杆件翻转检验同一判据）：小规格短杆的朝向证据不足，保持设计先验
            from .hypothesis import FLIP_MIN_B, FLIP_MIN_L
            V0 = self.init["V"]
            Lm = np.linalg.norm(V0[self.lay.mj] - V0[self.lay.mi], axis=1)
            bcur = x[self.sl["b"]] if "b" in self.sl else self.init["b"]
            gate = (bcur < FLIP_MIN_B) | (Lm < FLIP_MIN_L)
            s = self.sl["phi"]
            idx = np.arange(s.start, s.stop)[gate]
            lb[idx] = x[idx]; ub[idx] = x[idx]
        return list(zip(lb, ub))


# ====================================================================== 分阶段求解
@dataclass
class Stage:
    name: str
    free: tuple
    iters: int
    blur: float = 0.0
    spec: bool = False
    repairs: int = 1
    test: str = ""          # 阶段末逐杆件假设检验：""、"rot"（肢朝向）、"all"（肢朝向 + 存在/不存在）


DEFAULT_STAGES = (
    Stage("S1 粗配准（冻结截面、朝向与存在）", ("V", "app", "ext", "E"), 40, 0.03, False, 1, "rot"),
    Stage("S1 细配准", ("V", "phi", "d1", "d2", "app", "ext", "E"), 40, 0.012, False, 1, "rot"),
    Stage("S2 解冻肢宽", ("V", "b", "phi", "d1", "d2", "app", "ext", "E"), 60, 0.0, False, 2, "all"),
    Stage("S2 规格软吸附", ("V", "b", "phi", "d1", "d2", "app", "ext", "E"), 40, 0.0, True, 1),
    Stage("S3 拓扑（存在概率）", ("V", "b", "phi", "d1", "d2", "logit", "app", "ext", "E"), 50, 0.0, True, 2, "all"),
    Stage("S4 规格离散吸附后微调", ("V", "phi", "d1", "d2", "app", "ext", "E"), 40, 0.0, False, 1),
)


def solve(prob: Problem, x0=None, stages=DEFAULT_STAGES, log=print, snap_fn=None, prune_fn=None):
    """分阶段 L-BFGS-B。返回 (x, 历史, 各阶段末参数快照)。"""
    x = prob.x0() if x0 is None else x0.copy()
    hist, snaps = [], {}
    sc = prob.scale
    for st in stages:
        prob._spec_on = st.spec
        if st.name.startswith("S4") and snap_fn is not None:
            snaps["before_snap"] = x.copy()
            x = snap_fn(prob, x)
        free = tuple(k for k in st.free if (k != "ext" or prob.cfg.ext) and (k != "app" or prob.cfg.use_cam))
        for rp in range(st.repairs):
            t0 = time.time()
            npairs = prob.repair(x)
            frozen = None
            if prune_fn is not None and "logit" not in free:
                frozen = prune_fn(prob, x)
            bnds = [(lo / s if np.isfinite(lo) else None, hi / s if np.isfinite(hi) else None)
                    for (lo, hi), s in zip(prob.bounds(x, free, frozen), sc)]
            vg = value_and_grad(lambda z: prob.objective(z, st.blur))

            def fg(z):
                f, g = vg(z * sc)
                return f, g * sc
            it = max(5, int(st.iters * prob.cfg.iter_mult) // st.repairs)
            res = minimize(fg, x / sc, jac=True, method="L-BFGS-B", bounds=bnds,
                           options={"maxiter": it, "maxcor": 20, "ftol": 1e-13, "gtol": 1e-10})
            x = res.x * sc
            hist.append({"stage": st.name, "repair": rp, "f": float(res.fun), "nit": int(res.nit),
                         "nfev": int(res.nfev), "pairs": npairs, "t_s": round(time.time() - t0, 1)})
            log(f"  [{prob.cfg.label}] {st.name} #{rp}: f={res.fun:.5f} nit={res.nit} nfev={res.nfev} "
                f"pairs={npairs} t={time.time() - t0:.1f}s")
        if st.test and getattr(prob, "hyp_tests", True):
            from .hypothesis import member_tests
            t0 = time.time()
            prob.repair(x)
            hy = {"rot": ("rot90",), "grid": ("grid",), "all": ("rot90", "toggle")}[st.test]
            x, tres = member_tests(prob, x, hyps=hy, log=log)
            acc = {k: v["best"] for k, v in tres.items() if v["accepted"]}
            hist.append({"stage": st.name + " 假设检验", "accepted": acc, "n_tested": len(tres),
                         "detail": {k: (v["best"], round(v["delta"], 2), round(v["base"], 1)) for k, v in tres.items()},
                         "t_s": round(time.time() - t0, 1)})
        if st.name.startswith("S3") and prune_fn is not None:
            x = prune_fn(prob, x, apply=True)
        snaps[st.name] = x.copy()
    prob._spec_on = False
    return x, hist, snaps


def snap_widths(prob: Problem, x):
    """规格离散吸附：连续肢宽 → GB/T 706 最近肢宽档；同组（对称/同面板）多数一致化在 topology 中完成。"""
    s = prob.sl["b"]
    b = x[s]
    x = x.copy()
    x[s] = B_TABLE[np.argmin(np.abs(b[:, None] - B_TABLE[None]), 1)]
    return x
