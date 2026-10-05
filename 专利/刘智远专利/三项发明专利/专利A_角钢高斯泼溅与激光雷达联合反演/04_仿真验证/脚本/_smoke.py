# -*- coding: utf-8 -*-
"""开发用冒烟测试：构建场景、配对、计算目标函数与梯度并计时。"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from anglegs import synth as SY  # noqa: E402
from anglegs.optimize import CamData, Config, LidData, Problem  # noqa: E402
from anglegs.surfels import generate_np, make_layout  # noqa: E402
from autograd import value_and_grad  # noqa: E402

t0 = time.time()
rng = np.random.default_rng(1)
U = SY.build_universe("suspension", seed=1)
geom = SY.truth_geometry(U)
print("universe", U.n_members, "exist", U.exist.sum(), "plates", len(geom.P0), f"{time.time()-t0:.1f}s")
V0, b0, phi0, d10, d20, lg0 = SY.initial_state(U, rng)
cams, ext = SY.make_cameras(U.nodes_true[:, 2].max(), rng)
print("cams", len(cams))
alb = np.clip(rng.normal(0.55, 0.08, U.n_members), 0.3, 0.8)
O0, D0, DC, VEL, CI, MASK, GRAY, SKY, VAL, SIGK = [], [], [], [], [], [], [], [], [], []
t1 = time.time()
init_act = U.in_init | U.is_cand
for ci, c in enumerate(cams):
    uv = SY.sample_pixels(c, V0, U.mi[init_act], U.mj[init_act], b0[init_act], rng, n_band=5000, n_bg=1200)
    g, mk, fr, vd, sky = SY.render_pixels(c, uv, geom, alb, rng)
    dc = c.dcam(uv[:, 0], uv[:, 1])
    O0.append(np.repeat(c.C_nom[None], len(uv), 0)); D0.append(dc @ c.R_nom); DC.append(dc)
    VEL.append(np.repeat(c.vel[None], len(uv), 0)); CI.append(np.full(len(uv), ci))
    MASK.append(mk); GRAY.append(g); SKY.append(sky); VAL.append(vd); SIGK.append(np.full(len(uv), 0.45 / c.f))
cam = CamData(np.concatenate(O0), np.concatenate(D0), np.concatenate(DC), np.concatenate(VEL), np.concatenate(CI),
              np.stack([c.R_nom.T for c in cams]), np.concatenate(MASK), np.concatenate(GRAY), np.concatenate(SKY),
              np.concatenate(VAL), np.concatenate(SIGK))
print("cam rays", cam.n, "mask>0.5", float(np.mean(cam.mask > 0.5)), f"{time.time()-t1:.1f}s")
t2 = time.time()
lid = SY.simulate_lidar(geom, (12.0, 26.0, 40.0, 54.0), 28.0, rng, decim=0.05)
print("lidar kept", len(lid.o), "pulses", lid.n_pulses, "tower", int(np.sum(lid.kind == 0)), f"{time.time()-t2:.1f}s")
ret = lid.kind == 0
R = LidData(lid.o[ret], lid.d[ret], lid.rng_m[ret], lid.sig_div, lid.range_sigma)
lay = make_layout(V0, U.mi, U.mj)
print("surfels", lay.n_surfels)
init = dict(V=V0, b=b0, phi=phi0, d1=d10, d2=d20, logit=lg0)
prob = Problem(lay, len(V0), init, cam, R, None, Config(use_free=False))
x = prob.x0()
t3 = time.time()
print("pairs", prob.repair(x), f"{time.time()-t3:.1f}s")
fg = value_and_grad(lambda z: prob.objective(z, 0.0))
t4 = time.time()
f, g = fg(x)
print("fused f", f, "|g|", np.linalg.norm(g), f"value+grad {time.time()-t4:.1f}s")
t5 = time.time()
f, g = fg(x)
print(f"fused second value+grad {time.time()-t5:.1f}s")
fr = value_and_grad(lambda z: prob.objective_ref(z, 0.0))
t6 = time.time()
f2, g2 = fr(x)
print("ref f", f2, f"ref value+grad {time.time()-t6:.1f}s")
print("rel f diff", abs(f - f2) / abs(f2), "rel g diff", np.linalg.norm(g - g2) / np.linalg.norm(g2))
for k, s in prob.sl.items():
    a, b = g[s], g2[s]
    print(f"  block {k}: rel {np.linalg.norm(a - b) / max(np.linalg.norm(b), 1e-30):.2e}  |g|={np.linalg.norm(b):.3e}")
