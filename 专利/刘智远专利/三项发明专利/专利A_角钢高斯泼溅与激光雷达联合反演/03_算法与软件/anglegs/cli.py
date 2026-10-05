# -*- coding: utf-8 -*-
"""anglegs 命令行。

  python -m anglegs.cli demo  [--seed 1] [--out 结果目录]      合成塔端到端演示（PTM 式基线 vs 本发明）
  python -m anglegs.cli run   --variant 本发明 [--seed 1]       运行指定方法/消融
  python -m anglegs.cli list                                   列出可用方法与消融
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main(argv=None):
    ap = argparse.ArgumentParser(prog="anglegs", description="anglegs：桁架图参数化角钢高斯泼溅与激光雷达联合反演")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("demo", help="合成塔端到端演示")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--out", default="anglegs_demo_out")
    d.add_argument("--fast", action="store_true", help="缩小观测规模（约 1/4），用于快速检查")
    r = sub.add_parser("run", help="运行指定方法/消融")
    r.add_argument("--variant", default="本发明")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out", default="anglegs_run_out")
    sub.add_parser("list", help="列出方法与消融")
    a = ap.parse_args(argv)
    if a.cmd is None:
        ap.print_help()
        return 0
    from . import pipeline as PL
    if a.cmd == "list":
        for k in PL.VARIANTS:
            print(k)
        return 0
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    sc = PL.SceneCfg(seed=a.seed)
    if getattr(a, "fast", False):
        sc = PL.SceneCfg(seed=a.seed, n_band=2000, n_bg=400, n_ret_max=40000, n_free_max=20000, n_az=6, up_views=4)
    scene = PL.Scene(sc)
    r_ptm, _ = PL.ptm_metrics(scene)
    name = "本发明" if a.cmd == "demo" else a.variant
    run = PL.run_variant(scene, PL.VARIANTS[name])
    out = {"PTM 式基线": r_ptm, name: run["metrics"], "t_s": round(time.time() - t0, 1)}
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(PL.to_jsonable(out), fh, ensure_ascii=False, indent=1)
    m = run["metrics"]
    print(f"PTM 式基线 节点RMSE={r_ptm['RMSEn_m']:.4f} m；{name} 节点RMSE={m['RMSEn_m']:.4f} m，"
          f"肢宽MAE={m['width_MAE_mm']:.1f} mm，朝向正确率={m['orient_correct_rate']:.3f}，存在AUC={m['exist_AUC']:.4f}")
    print("结果写入", os.path.join(a.out, "result.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
