# -*- coding: utf-8 -*-
"""开发：E 端到端单次运行（含对比方法）。用法：_dev_e.py [duration] [U10] [seed]"""
import os
import sys
import time
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from trussvid import pipeline as PL  # noqa: E402

t0 = time.time()
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 1200.0
U10 = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
cfg = PL.ExpCfg(duration=dur, U10=U10, seed=seed)
tr = PL.TruthCache.get(cfg.U10, cfg.duration, cfg.fps, cfg.seed)
print("真值频率", [round(float(f), 3) for f in tr.freq[:12]], "评价模态", [k + 1 for k in tr.info["eval_modes"]],
      f"{time.time() - t0:.1f}s")
print("标定", {k: round(v["std_px"], 4) for k, v in PL.calibration("gradient", cfg.band_len).items()})
res = PL.run(cfg, baselines=True)
for p in res["per_mode"]:
    print("  ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()})
print("  与名义模型 MAC", [round(v, 3) for v in res["mac_vs_nominal"]])
for v in [replace(cfg, label="不白化", whiten=False),
          replace(cfg, label="单相机 az0", n_cams=1, azimuths_deg=(0.0,))]:
    PL.run(v)
print(f"total {time.time() - t0:.0f}s")
