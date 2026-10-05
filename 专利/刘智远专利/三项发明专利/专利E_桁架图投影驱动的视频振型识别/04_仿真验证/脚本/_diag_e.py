# -*- coding: utf-8 -*-
"""诊断：各阶真值模态在像面观测中的信噪比、反投影后模态坐标的信噪比。"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from trussvid import operator as OP  # noqa: E402
from trussvid import pipeline as PL  # noqa: E402
from trussvid import synth as SY  # noqa: E402
from trussvid.bands import band_samples, visible_members  # noqa: E402

dur = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
U10 = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
t0 = time.time()
calib = SY.calibrate_band_noise()
cfg = PL.ExpCfg(duration=dur, U10=U10)
tr = PL.TruthCache.get(cfg.U10, cfg.duration, cfg.fps, cfg.seed)
n = len(tr.g.nodes)
Ht = tr.g.nodes[:, 2].max()
print("真值频率", np.round(tr.freq, 3), "阻尼", np.round(tr.zeta, 4), f"{time.time() - t0:.1f}s")
Phi_t = OP.translational(tr.phi, n)
top = np.argsort(-tr.g.nodes[:, 2])[:4]
U = tr.node_disp()
print("塔顶位移 RMS (mm) xyz", np.round(1e3 * U[:, top, :].std(0).mean(0), 3))
for k in range(8):
    uk = (tr.q[:, k:k + 1] @ Phi_t[:, k:k + 1].T).reshape(len(tr.t), n, 3)
    print(f"  模态{k + 1} f={tr.freq[k]:.3f}  塔顶 RMS(mm)={1e3 * np.sqrt((uk[:, top, :] ** 2).sum(-1).mean()):.3f}"
          f"  全塔最大 RMS(mm)={1e3 * np.sqrt((uk ** 2).sum(-1).mean(0)).max():.3f}")
cams = PL.make_cams(cfg, Ht)
f_nom, phi_nom = tr.fem_nom.modes(cfg.n_basis)
Phi = OP.translational(phi_nom, n)
As, ws, At = [], [], []
for cam in cams:
    vis = visible_members(tr.g, tr.geom, cam)
    S = band_samples(tr.g, cam, vis, spacing_px=cfg.spacing_px)
    Hm = OP.obs_rows(S, n)
    sig = PL.band_noise_model(S, calib)
    As.append(Hm @ Phi); ws.append(1 / sig ** 2); At.append(Hm @ Phi_t)
    print(f"  {cam.name}: f={cam.f:.0f}px GSD@100m={1e3 * cfg.distance / cam.f:.1f}mm  可见杆件 {len(vis)} 采样带 {S.n}")
A = np.vstack(As); w = np.concatenate(ws); Atr = np.vstack(At)
N = (A.T * w) @ A
cov = np.linalg.inv(N)
# 真值模态坐标在名义基下的等效坐标：q_nom = pinv(Phi) Phi_t q
T = np.linalg.lstsq(Phi, Phi_t, rcond=None)[0]           # (16, 12)
for k in range(8):
    qk = tr.q[:, k].std()
    # 第 k 阶真值模态的像面观测能量对噪声：||A_t[:,k]||_W * rms(q_k)
    snr = qk * np.sqrt(np.sum(w * Atr[:, k] ** 2))
    print(f"  模态{k + 1}: 像面观测 SNR(整体)={snr:.2f}")
print(f"{time.time() - t0:.1f}s")
