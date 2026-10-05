# -*- coding: utf-8 -*-
"""示例：组合变体塔（高低腿+缺材+遮挡），220 kV，比较纯几何 NBV 与本发明。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from livenbv import pipeline as P  # noqa: E402

ctx = P.Context("combined", kv=220.0, sigma_pos=0.5)
for name, fn in (("无补测", P.run_none), ("纯几何NBV", lambda c: P.run_nbv(c, False)),
                 ("本发明", lambda c: P.run_nbv(c, True))):
    m = fn(ctx)["metrics"]
    print(f"{name}: 覆盖率 {m['coverage']:.3f} 低置信 {m['n_low']} 航程 {m['path_m']:.0f} m "
          f"塔顶位移误差 {m['tip_err_pct']:.2f}% 违规 {m['violations']}")
