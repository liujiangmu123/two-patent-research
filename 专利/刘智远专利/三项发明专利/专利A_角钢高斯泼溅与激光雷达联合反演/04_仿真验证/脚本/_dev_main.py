# -*- coding: utf-8 -*-
"""开发：单次主实验（本发明 + PTM 式基线），检查收敛与指标。"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from anglegs import pipeline as PL  # noqa: E402

t0 = time.time()
sc = PL.SceneCfg(seed=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
scene = PL.Scene(sc)
r_ptm, r_init = PL.ptm_metrics(scene)
keys = ("RMSEn_m", "RMSEn_main_m", "RMSEn_diagonal_m", "RMSEn_auxiliary_m", "width_MAE_mm", "width_class_acc",
        "orient_err_deg_median", "orient_correct_rate", "delta_err_mm", "exist_AUC", "damaged_removed",
        "falseneg_recovered", "spurious_rejected", "NGED_main", "NGED_diagonal", "NGED_auxiliary")
print("初始 ", {k: round(r_init[k], 4) if isinstance(r_init[k], float) else r_init[k] for k in keys})
print("PTM  ", {k: round(r_ptm[k], 4) if isinstance(r_ptm[k], float) else r_ptm[k] for k in keys})
name = sys.argv[2] if len(sys.argv) > 2 else "本发明"
run = PL.run_variant(scene, PL.VARIANTS[name], fisher_M=0)
m = run["metrics"]
print(name, {k: round(m[k], 4) if isinstance(m[k], float) else m[k] for k in keys})
print("ext est", np.round(m["ext_est"], 5), "truth omega", np.round(scene.ext_true.omega, 5), "lever",
      scene.ext_true.lever, "dt", scene.ext_true.dt)
print("topology", m["topology"])
print(f"total {time.time() - t0:.1f}s")
