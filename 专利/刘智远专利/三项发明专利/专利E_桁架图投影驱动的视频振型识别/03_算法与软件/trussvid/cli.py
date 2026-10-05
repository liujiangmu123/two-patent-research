# -*- coding: utf-8 -*-
"""trussvid 命令行。

  python -m trussvid.cli calib                          采样带亚像素测量噪声标定（短片段渲染）
  python -m trussvid.cli demo [--duration 300] [--out d] 三台相机端到端演示（含对比方法）
  python -m trussvid.cli run --cams 2 --az 20 110 ...    自定义布站运行
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="trussvid", description="trussvid：桁架图投影驱动的视频运行模态识别")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("calib", help="采样带亚像素测量噪声标定")
    d = sub.add_parser("demo", help="三台相机端到端演示")
    d.add_argument("--duration", type=float, default=300.0)
    d.add_argument("--out", default="trussvid_demo_out")
    r = sub.add_parser("run", help="自定义布站运行")
    r.add_argument("--cams", type=int, default=3)
    r.add_argument("--az", type=float, nargs="+", default=[20.0, 110.0, 200.0])
    r.add_argument("--distance", type=float, default=100.0)
    r.add_argument("--fps", type=float, default=50.0)
    r.add_argument("--duration", type=float, default=300.0)
    r.add_argument("--no-shake-comp", action="store_true")
    r.add_argument("--no-sync-corr", action="store_true")
    r.add_argument("--out", default="trussvid_run_out")
    a = ap.parse_args(argv)
    if a.cmd is None:
        ap.print_help()
        return 0
    from . import pipeline as PL
    from . import synth as SY
    calib = SY.calibrate_band_noise()
    if a.cmd == "calib":
        print(json.dumps(calib, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "demo":
        cfg = PL.ExpCfg(duration=a.duration)
        res = PL.run(cfg, calib, baselines=True)
    else:
        cfg = PL.ExpCfg(n_cams=a.cams, azimuths_deg=tuple(a.az), distance=a.distance, fps=a.fps, duration=a.duration,
                        shake_comp=not a.no_shake_comp, sync_corr=not a.no_sync_corr)
        res = PL.run(cfg, calib)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)
    print("结果写入", os.path.join(a.out, "result.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
