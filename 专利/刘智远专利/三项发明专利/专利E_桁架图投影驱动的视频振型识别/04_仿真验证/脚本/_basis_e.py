# -*- coding: utf-8 -*-
"""诊断：名义振型基对真值整体模态的表示能力（投影 MAC），比较单一名义模型 n 阶与截面集合模型 SVD 压缩基。"""
import copy
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from trussvid import oma as OMA  # noqa: E402
from trussvid import operator as OP  # noqa: E402
from trussvid import synth as SY  # noqa: E402
from towerkit import fem as F  # noqa: E402
from towerkit import sections as S  # noqa: E402

t0 = time.time()
tr = SY.build_truth(duration=60.0)
n = len(tr.g.nodes)
Pt = OP.translational(tr.phi, n)
idx = tr.info["eval_modes"]
print("评价模态", [k + 1 for k in idx], np.round(tr.freq[idx], 3))


def proj_mac(B):
    Qb, _ = np.linalg.qr(B)
    return [OMA.mac(Pt[:, k], Qb @ (Qb.T @ Pt[:, k])) for k in idx]


for nb in (12, 16, 24, 32):
    f, ph = tr.fem_nom.modes(nb)
    print(f"名义 {nb} 阶", np.round(proj_mac(OP.translational(ph, n)), 3))

# 截面集合：主/斜/辅材截面在若干规格档内随机取值（含按长细比/高度变化），各取前 12 阶，SVD 压缩
rng = np.random.default_rng(5)
names = S.ANGLE_ORDER if hasattr(S, "ANGLE_ORDER") else sorted(S.ANGLES)
cols = []
for r in range(12):
    g = copy.deepcopy(tr.g_nom)
    secs = []
    for e in range(g.n_members):
        base = g.sec[e]
        k = int(rng.integers(-6, 3))
        try:
            secs.append(S.step(base, k))
        except Exception:
            secs.append(base)
    g.sec = secs
    fm = F.FEModel(g)
    fm.fix_base()
    f, ph = fm.modes(12)
    cols.append(OP.translational(ph, n))
E = np.hstack(cols)
U, s, _ = np.linalg.svd(E / np.linalg.norm(E, axis=0, keepdims=True), full_matrices=False)
for nb in (16, 24, 32):
    print(f"集合 SVD {nb} 维", np.round(proj_mac(U[:, :nb]), 3))
print(f"{time.time() - t0:.0f}s")
