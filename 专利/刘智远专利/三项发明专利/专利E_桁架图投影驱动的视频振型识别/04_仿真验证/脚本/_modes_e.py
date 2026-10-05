# -*- coding: utf-8 -*-
"""诊断：真值模型前 16 阶模态的有效质量比（x、y、z 平动与绕 z 扭转）与振型特征。"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from trussvid import synth as SY  # noqa: E402,F401
from towerkit import fem as F  # noqa: E402
from towerkit import tower as T  # noqa: E402

spec = T.TowerSpec.preset("suspension")
g = T.build_tower(spec)
T.assign_sections(g, spec)
fem = F.FEModel(g)
fem.fix_base()
freq, phi = fem.modes(16)
M = fem.M()
X = g.nodes
n = len(X)
fr = ~fem.fixed
r = {}
for name in ("x", "y", "z", "rz"):
    v = np.zeros(fem.ndof)
    for k in range(n):
        if name == "x":
            v[6 * k] = 1
        elif name == "y":
            v[6 * k + 1] = 1
        elif name == "z":
            v[6 * k + 2] = 1
        else:
            v[6 * k] = -X[k, 1]; v[6 * k + 1] = X[k, 0]; v[6 * k + 5] = 1
    v[~fr] = 0
    r[name] = v
tot = {k: float(v @ (M @ v)) for k, v in r.items()}
Ph = phi.reshape(n, 6, -1)[:, :3, :]
top = np.argsort(-X[:, 2])[:20]
print("总质量 t", fem.total_mass() / 1e3)
for j in range(16):
    p = phi[:, j]
    em = {k: float((p @ (M @ v)) ** 2 / tot[k]) for k, v in r.items()}
    a = np.linalg.norm(Ph[:, :, j], axis=1)
    kmax = int(np.argmax(a))
    print(f"{j + 1:2d} f={freq[j]:.3f}  有效质量比 x={em['x']:.3f} y={em['y']:.3f} z={em['z']:.3f} rz={em['rz']:.3f}"
          f"  最大位移节点 z={X[kmax, 2]:.1f} m (x={X[kmax, 0]:.1f}, y={X[kmax, 1]:.1f})  类型 {g.ntype[kmax]}"
          f"  顶部/最大={a[top].mean() / a.max():.2f}")
