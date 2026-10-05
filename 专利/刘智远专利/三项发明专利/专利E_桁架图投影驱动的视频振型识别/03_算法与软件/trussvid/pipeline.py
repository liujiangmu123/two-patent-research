# -*- coding: utf-8 -*-
"""端到端实验：真值风振响应 → 多相机采样带法向位移（含测量噪声、大气湍流抖动、相机自振、残余时间偏差）
→ 自振补偿、时间偏差估计与校正 → 观测算子联合反投影（残差重加权）→ SSI-COV → 三维节点振型与真值对比；
以及人工靶点（+SEREP 扩展）、全部采样带位移 + 盲源分离等对比方法。"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np

from . import baselines as BL
from . import oma as OMA
from . import operator as OP
from . import shake as SH
from . import synth as SY
from .bands import band_samples, visible_members
from .camera import ring_cameras, shake_series


@dataclass
class ExpCfg:
    n_cams: int = 3
    distance: float = 100.0
    azimuths_deg: tuple = (20.0, 110.0, 200.0)
    W: int = 3008                          # 1240 万像素全局快门相机竖幅安装（4128×3008）
    H: int = 4128
    fps: float = 50.0
    duration: float = 1200.0               # 20 min 记录（约 1800 倍基频周期）
    U10: float = 10.0
    method: str = "gradient"               # 采样带位移估计方法（gradient | phase），决定标定噪声
    band_len: int = 24                     # 采样带沿杆件长度（像素行数）
    band_noise_scale: float = 1.0          # 采样带噪声倍率（相对标定值）
    whiten: bool = True                    # 以反投影噪声协方差白化模态坐标后再做随机子空间识别
    turb_urad: float = 3.0                 # 近地面大气湍流到达角抖动 RMS（μrad）
    shake_rot_urad: float = 15.0           # 相机自振转角 RMS（μrad）
    tau_ms: tuple = (0.0, 1.2, -0.8)       # 各相机残余时间偏差（ms）；秒脉冲触发后的残差量级
    shake_comp: str = "bg"                 # none | bg（远景背景点）| imu（仅陀螺）| fusion（背景点+陀螺）
    joint_shake: bool = True               # 相机转动与模态坐标联合反投影（塔基固定边界 + 背景点约束）
    n_bg: int = 24
    bg_noise_px: float = 0.03
    gyro_arw: float = 2.6e-5               # 陀螺角随机游走（rad/√s）
    sync_corr: bool = True
    reweight: bool = True
    n_basis: int = 16                      # 名义振型基阶数
    lam: float = 1e-4
    spacing_px: float = 30.0
    n_eval: int = 0                        # 0 = 全部评价模态（有效质量比 ≥2% 的整体模态）
    seed: int = 0
    label: str = "本发明"


class TruthCache:
    _c = {}

    @classmethod
    def get(cls, U10, duration, fps, seed, stiff_scale=None):
        k = (U10, duration, fps, seed, None if not stiff_scale else tuple(sorted(stiff_scale.items())))
        if k not in cls._c:
            if len(cls._c) > 3:
                cls._c.pop(next(iter(cls._c)))
            cls._c[k] = SY.build_truth(U10=U10, duration=duration, fps=fps, seed=seed, stiff_scale=stiff_scale)
        return cls._c[k]


_CALIB = {}


def calibration(method="gradient", band_len=24):
    key = (method, int(band_len))
    if key not in _CALIB:
        _CALIB[key] = SY.calibrate_band_noise(method=method, band_len=int(band_len))
    return _CALIB[key]


def make_cams(cfg: ExpCfg, H_tower):
    az = np.deg2rad(np.asarray(cfg.azimuths_deg[:cfg.n_cams]))
    return ring_cameras(cfg.n_cams, distance=cfg.distance, height=1.5, target=(0, 0, 0.5 * H_tower), azimuths=az,
                        W=cfg.W, H=cfg.H, fit_height=H_tower + 2.0, fit_distance=cfg.distance)


def band_noise_model(samples, calib, scale=1.0):
    """按采样带投影宽度插值标定的法向位移噪声（px）。"""
    ws = np.array(sorted(calib))
    sd = np.array([calib[w]["std_px"] for w in ws])
    return scale * np.interp(samples.width_px, ws, sd)


def run(cfg: ExpCfg, calib=None, log=print, baselines=False, keep=False, truth=None):
    """返回结果字典；keep=True 时在 res['_arrays'] 中保留作图所需数组。"""
    t0 = time.time()
    calib = calib or calibration(cfg.method, cfg.band_len)
    rng = np.random.default_rng(cfg.seed + 11)
    tr = truth or TruthCache.get(cfg.U10, cfg.duration, cfg.fps, cfg.seed)
    g = tr.g
    n = len(g.nodes)
    Ht = float(g.nodes[:, 2].max())
    cams = make_cams(cfg, Ht)
    dt = 1.0 / cfg.fps
    nt = len(tr.t)
    f_nom, phi_nom = tr.fem_nom.modes(cfg.n_basis)
    Phi = OP.translational(phi_nom, n)
    Phi_true = OP.translational(tr.phi, n)
    Ys, As, ws, samp_all, cam_stats, Atr = [], [], [], [], [], []
    om_true, om_hats, Gns, Gbgs, Fbgs = [], [], [], [], []
    for ci, cam in enumerate(cams):
        vis = visible_members(g, tr.geom, cam)
        S = band_samples(g, cam, vis, spacing_px=cfg.spacing_px)
        Hm = OP.obs_rows(S, n)
        A_true = Hm @ Phi_true
        sig = band_noise_model(S, calib, cfg.band_noise_scale)
        if cfg.n_cams == 0 or S.n == 0:
            raise ValueError(f"{cam.name} 无可见采样带")
        om, _ = shake_series(tr.t, rot_rms=cfg.shake_rot_urad * 1e-6, seed=cfg.seed * 10 + ci)
        G_s = cam.rotation_flow_jacobian(S.uv)
        gn = np.einsum("sij,si->sj", G_s, S.nrm)                 # 采样点法向位移对相机转角的灵敏度 (n_obs,3)
        tau = 1e-3 * (cfg.tau_ms[ci] if ci < len(cfg.tau_ms) else 0.0)
        Y = SY.measure(A_true, tr.q, sig, rng, tau=tau, dt=dt, turb_px=cfg.turb_urad * 1e-6 * cam.f,
                       shake_om=om, shake_gn=gn)
        shake_rms = float(np.sqrt(np.mean((om[::5] @ gn.T) ** 2)))
        om_hat = np.zeros_like(om)
        n_bg = 0
        G_bg = flow_bg = None
        if cfg.shake_comp != "none":
            bg = SH.background_points(cam, n=cfg.n_bg, rng=rng, avoid_uv=S.uv)
            n_bg = len(bg)
            om_bg = None
            if n_bg >= 3:
                G_bg = cam.rotation_flow_jacobian(bg)
                flow_bg = np.einsum("bij,tj->tbi", G_bg, om) + rng.normal(0, cfg.bg_noise_px, (nt, n_bg, 2))
                om_bg = SH.estimate_rotation(G_bg, flow_bg)
            if cfg.shake_comp in ("imu", "fusion"):
                gyro = SH.gyro_series(om, dt, rng, arw=cfg.gyro_arw)
                if cfg.shake_comp == "fusion" and om_bg is not None:
                    om_hat = SH.fuse_imu(om_bg, gyro, dt)
                else:
                    ang = np.cumsum(gyro, 0) * dt
                    om_hat = OP.bandpass(ang, cfg.fps, (0.3, 0.45 * cfg.fps))
            elif om_bg is not None:
                om_hat = om_bg
            for s in range(0, Y.shape[1], 256):
                Y[:, s:s + 256] -= (om_hat @ gn[s:s + 256].T).astype(np.float32)
        om_true.append(om); om_hats.append(om_hat)
        Gns.append(gn)
        Gbgs.append(None if G_bg is None else G_bg.reshape(-1, 3))
        # 背景点流残差（已扣除 om_hat 后）作为联合补偿的附加观测
        Fbgs.append(None if flow_bg is None else (flow_bg.reshape(nt, -1) - om_hat @ G_bg.reshape(-1, 3).T).astype(np.float32))
        Ys.append(Y); As.append(Hm @ Phi); ws.append(1.0 / sig ** 2); samp_all.append(S); Atr.append(A_true)
        st = {"cam": cam.name, "n_visible": int(len(vis)), "n_bands": int(S.n), "noise_med_px": float(np.median(sig)),
              "signal_rms_px": float(np.sqrt(np.mean((tr.q[::5] @ A_true.T) ** 2))),
              "shake_rms_px": shake_rms,
              "shake_res_bg_urad": float(1e6 * np.sqrt(np.mean((om - om_hat) ** 2))), "n_bg": int(n_bg),
              "f_px": float(cam.f), "gsd_mm": float(1e3 * cfg.distance / cam.f)}
        cam_stats.append(st)
        log(f"  {cam.name}: 可见杆件 {st['n_visible']}，采样带 {st['n_bands']}，噪声中位 {st['noise_med_px']:.3f} px，"
            f"信号 RMS {st['signal_rms_px']:.3f} px，自振诱导 {st['shake_rms_px']:.3f} px，背景点补偿后残余转角 "
            f"{st['shake_res_bg_urad']:.2f} μrad")
    C = len(cams)
    m = Phi.shape[1]
    joint = cfg.joint_shake and cfg.shake_comp != "none"
    wbgs = [1.0 / cfg.bg_noise_px ** 2] * C

    def solve(Ys_, ws_):
        """返回 (Q, Ω 列表, P, A_aug, w_aug, nb)。joint=False 时 Ω 为零。"""
        if joint:
            A_aug, w_aug, P, nb = OP.joint_operator(As, Gns, Gbgs, ws_, wbgs, cfg.lam)
            X = np.hstack([Y_ for Y_ in Ys_] + [F for F in Fbgs if F is not None])
            Z = OP.project(X, P)
            return Z[:, :m], [Z[:, m + 3 * c:m + 3 * c + 3] for c in range(C)], P, A_aug, w_aug, nb
        A_ = np.vstack(As); w_ = np.concatenate(ws_)
        _, P = OP.reconstruct(np.zeros((1, A_.shape[0])), A_, w_, cfg.lam)
        return OP.project(np.hstack(Ys_), P), [np.zeros((nt, 3))] * C, P, A_, w_, A_.shape[0]

    # ① 残余时间偏差估计与频域相位校正（相机 1 为参考；在背景点初步补偿后的数据上进行，
    #    以免联合反投影中的相机转动分量吸收时间偏差引起的 −τ·A·q̇ 特征）
    tau_est = np.zeros(C)
    if cfg.sync_corr and C > 1:
        tau_est = OP.estimate_offsets(Ys, As, ws, dt, cfg.lam, seed=cfg.seed)
        for c in range(1, C):
            OP.frac_delay_inplace(Ys[c], -tau_est[c], dt)
            if Fbgs[c] is not None:
                OP.frac_delay_inplace(Fbgs[c], -tau_est[c], dt)
    # ② 模态坐标与相机转动联合反投影 + 残差重加权
    Q, Om, Pm, A_aug, w_aug, nb = solve(Ys, ws)
    if cfg.reweight:
        A_b = np.vstack(As)
        Yall = np.hstack(Ys)
        if joint:
            # 残差需扣除联合估计的转动分量：在增广观测上计算
            Gblk = np.zeros((A_b.shape[0], 3 * C)); r0 = 0
            for c in range(C):
                Gblk[r0:r0 + As[c].shape[0], 3 * c:3 * c + 3] = Gns[c]; r0 += As[c].shape[0]
            wnew = OP.residual_weights(Yall, np.hstack([A_b, Gblk]), np.hstack([Q] + Om), fs=cfg.fps,
                                       band=(0.3, min(15.0, 0.45 * cfg.fps)))
        else:
            wnew = OP.residual_weights(Yall, A_b, Q, fs=cfg.fps, band=(0.3, min(15.0, 0.45 * cfg.fps)))
        del Yall
        o = 0
        ws = []
        for c in range(C):
            ws.append(wnew[o:o + As[c].shape[0]]); o += As[c].shape[0]
        Q, Om, Pm, A_aug, w_aug, nb = solve(Ys, ws)
    for c in range(C):
        om_hats[c] = om_hats[c] + Om[c]
        cam_stats[c]["shake_res_urad"] = float(1e6 * np.sqrt(np.mean((om_true[c] - om_hats[c]) ** 2)))
    om_res = [om_true[c] - om_hats[c] for c in range(C)]
    Sig_q = OP.coord_noise_cov(Pm[:m], w_aug)
    Pm = Pm[:m]
    A = np.vstack(As); w = np.concatenate(ws)
    Y = np.hstack(Ys)
    Ys = None
    cond = OP.cond_number(A_aug, w_aug)
    Lw = None
    if cfg.whiten:
        Qw, Lw = OP.whiten(Q, Sig_q)
        modes = OMA.identify(Qw, cfg.fps)
        for m in modes:
            m["phi"] = Lw @ m["phi"]
    else:
        modes = OMA.identify(Q, cfg.fps)
    shapes = np.stack([Phi @ m["phi"] for m in modes], 1) if modes else np.zeros((3 * n, 0))
    idx = eval_index(tr, cfg)
    match = OMA.match_modes(modes, tr.freq[idx], Phi_true[:, idx], shapes, mac_min=0.0)
    tau_true = [1e-3 * (cfg.tau_ms[c] if c < len(cfg.tau_ms) else 0.0) for c in range(len(cams))]
    res = summarize(cfg.label, tr, modes, match, idx, extra={
        "cond": cond, "tau_true_ms": [1e3 * (t - tau_true[0]) for t in tau_true],
        "tau_est_ms": [1e3 * t for t in tau_est], "n_obs": int(A.shape[0]), "cams": cam_stats,
        "cfg": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()}})
    # 识别振型与有限元（名义）振型的 MAC（权利要求 1 S7 的输出，用于模型修正与状态评估）
    res["mac_vs_nominal"] = [float(max(OMA.mac(shapes[:, m[1]], Phi[:, j]) for j in range(Phi.shape[1])))
                             for m in match]
    res["t_s"] = round(time.time() - t0, 1)
    log(f"  [{cfg.label}] 频率识别（±1%）{res['n_freq_1pct']}/{len(idx)}，MAC≥0.9 {res['n_mac90']} 阶，平均 MAC（未识别计 0）"
        f"{res['mac_mean_all']:.3f}，各阶 MAC {np.round(res['mac_per_true_mode'], 3).tolist()}，频率误差 "
        f"{res['f_err_mean']:.4f}，阻尼相对误差 {res['zeta_err_mean']:.3f}，条件数 {cond:.1f}，"
        f"τ̂={np.round(res['tau_est_ms'], 2).tolist()} ms  {res['t_s']:.1f}s")
    if baselines:
        em_nom = SY.effective_mass(tr.fem_nom, phi_nom)
        res["baselines"] = run_baselines(cfg, tr, cams, Y, om_res, tau_true, tau_est, rng, log, Phi, em_nom)
    if keep:
        res["_arrays"] = {"Q": Q, "modes": modes, "shapes": shapes, "Phi": Phi, "Phi_true": Phi_true, "f_nom": f_nom,
                          "samples": samp_all, "cams": cams, "Y0": np.asarray(Y[:, :8], float), "A": A, "w": w,
                          "match": match, "om_res": om_res, "A_true": np.vstack(Atr), "Pm": Pm, "Sig_q": Sig_q}
    return res


def eval_index(tr, cfg=None):
    """评价模态集（真值模态序号，0 起）：有效质量比 ≥2% 且 ≤8 Hz 的整体模态；局部支撑杆件模态不参与评价。"""
    idx = list(tr.info.get("eval_modes") or range(8))
    if cfg is not None and cfg.n_eval:
        idx = idx[:cfg.n_eval]
    return np.asarray(idx, int)


def summarize(label, tr, modes, match, idx, extra=None):
    """match 为 match_modes(..., mac_min=0) 的结果（真值模态以 idx 中的位置编号）：每个评价模态在 ±5% 频率内取
    MAC 最大的识别模态。指标：频率识别阶数 n_freq_id、MAC≥0.6/0.8/0.9 阶数、平均 MAC（未识别计 0）、
    已识别阶的频率与阻尼相对误差。"""
    idx = np.asarray(idx, int)
    fe = [m[2] for m in match]
    mc = [m[3] for m in match]
    zt = tr.zeta[idx]
    ze = [abs(modes[m[1]]["zeta"] - zt[m[0]]) / zt[m[0]] for m in match]
    mac_all = np.zeros(len(idx))
    for m in match:
        mac_all[m[0]] = m[3]
    fid = [mm["f"] for mm in modes]
    n1 = int(sum(1 for f in tr.freq[idx] if any(abs(x - f) / f < 0.01 for x in fid)))
    out = {"label": label, "n_identified": len(modes), "n_eval": int(len(idx)), "eval_modes": (idx + 1).tolist(),
           "n_freq_id": len(match), "n_freq_1pct": n1, "n_matched": int(np.sum(mac_all >= 0.6)),
           "n_mac80": int(np.sum(mac_all >= 0.8)), "n_mac90": int(np.sum(mac_all >= 0.9)),
           "mac_mean_all": float(mac_all.mean()), "mac_per_true_mode": mac_all.tolist(),
           "matched_true_modes": [int(idx[m[0]] + 1) for m in match],
           "f_err_mean": float(np.mean(fe)) if fe else float("nan"),
           "f_err_max": float(np.max(fe)) if fe else float("nan"),
           "mac_mean": float(np.mean(mc)) if mc else float("nan"),
           "mac_min": float(np.min(mc)) if mc else float("nan"),
           "zeta_err_mean": float(np.mean(ze)) if ze else float("nan"),
           "f_true": tr.freq[idx].tolist(), "zeta_true": zt.tolist(),
           "per_mode": [{"mode": int(idx[m[0]] + 1), "f_true": float(tr.freq[idx[m[0]]]), "f_est": modes[m[1]]["f"],
                         "f_err": float(m[2]), "mac": float(m[3]), "zeta_true": float(zt[m[0]]),
                         "zeta_est": modes[m[1]]["zeta"], "zeta_rel_err": float(abs(modes[m[1]]["zeta"] - zt[m[0]]) / zt[m[0]])}
                        for m in match]}
    if extra:
        out.update(extra)
    return out


def target_nodes(g, n_targets=4):
    """人工靶点：同一根角主材上自下而上 4 个高度的节点（含塔顶附近）。"""
    X = g.nodes
    n = len(X)
    cand = [k for k in range(n) if X[k, 0] > 0 and X[k, 1] > 0 and abs(abs(X[k, 0]) - abs(X[k, 1])) < 0.3]
    cand = sorted(cand, key=lambda k: X[k, 2])
    return [cand[int(r * (len(cand) - 1))] for r in np.linspace(0.35, 1.0, n_targets)]


def run_baselines(cfg, tr, cams, Yall, om_res, tau_true, tau_est, rng, log, Phi, em_nom):
    out = {}
    g = tr.g
    n = len(g.nodes)
    idx = eval_index(tr, cfg)
    Phi_true = OP.translational(tr.phi, n)
    dt = 1.0 / cfg.fps
    # ① 人工靶点：同一角主材 4 个节点，靶点亚像素跟踪噪声 0.01 px，与本发明相同的自振补偿与同步校正残差
    pick = target_nodes(g)
    U = tr.node_disp(pick)
    tau_res = [tau_true[c] - tau_true[0] - tau_est[c] for c in range(len(cams))]
    est = BL.target_triangulate(cams, g.nodes[pick], U, rng, sig_px=0.01, shake_res=om_res, tau_res=tau_res, dt=dt)
    yt = est.reshape(len(est), -1)
    md = OMA.identify(yt, cfg.fps)
    rows = np.concatenate([[3 * k, 3 * k + 1, 3 * k + 2] for k in pick])
    sh = np.stack([m["phi"] for m in md], 1) if md else np.zeros((len(rows), 0))
    # SEREP 扩展只用名义模型的整体模态（有效质量比 ≥2%），与本发明使用同一名义有限元先验
    keep = [k for k in range(len(em_nom)) if em_nom[k].max() >= 0.02][:len(rows)]
    sh_full = BL.serep_expand(sh, Phi[rows], Phi, keep=keep) if md else np.zeros((3 * n, 0))
    mt_loc = OMA.match_modes(md, tr.freq[idx], Phi_true[rows][:, idx], sh, mac_min=0.0)
    mt_full = OMA.match_modes(md, tr.freq[idx], Phi_true[:, idx], sh_full, mac_min=0.0)
    r1 = summarize("人工靶点(4 点)+SEREP 扩展", tr, md, mt_full, idx,
                   {"note": "三维全节点 MAC 由 4 靶点 12 自由度经名义振型基前 8 阶 SEREP 扩展后计算",
                    "mac_local_per_true_mode": summarize("", tr, md, mt_loc, idx)["mac_per_true_mode"]})
    out["人工靶点"] = r1
    log(f"  [人工靶点] 频率识别 {r1['n_freq_id']}/{len(idx)}，扩展后各阶 MAC {np.round(r1['mac_per_true_mode'], 3).tolist()}，"
        f"靶点处局部 MAC {np.round(r1['mac_local_per_true_mode'], 3).tolist()}")
    # ② 全部采样带位移 + 盲源分离（不使用观测算子，无三维振型）
    Yall = OP.bandpass(np.asarray(Yall[:, ::max(1, Yall.shape[1] // 400)], float), cfg.fps, (0.4, 10.0))
    S, _ = BL.sobi(Yall, n_src=12)
    sm = BL.source_modes(S, cfg.fps)
    used, fe, ze, ks = set(), [], [], []
    for k in idx:
        cands = [(abs(s["f"] - tr.freq[k]) / tr.freq[k], j) for j, s in enumerate(sm) if j not in used]
        if cands:
            e, j = min(cands)
            if e < 0.01:
                used.add(j); fe.append(e); ze.append(abs(sm[j]["zeta"] - tr.zeta[k]) / tr.zeta[k]); ks.append(int(k + 1))
    out["盲源分离"] = {"label": "全部采样带位移+SOBI", "n_freq_1pct": len(fe), "n_eval": int(len(idx)), "matched_true_modes": ks,
                     "f_err_mean": float(np.mean(fe)) if fe else None,
                     "zeta_err_mean": float(np.mean(ze)) if ze else None, "mac_mean_all": None,
                     "note": "仅得频率与像面二维振型，无法输出三维节点振型"}
    log(f"  [盲源分离] 频率匹配（±1%）{len(fe)}/{len(idx)} 阶 {ks}")
    return out
