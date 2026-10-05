# -*- coding: utf-8 -*-
"""诊断：反投影模态坐标中各评价模态的信噪比与 Q 空间可分性；不同 SSI 参数下的识别结果。"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from trussvid import oma as OMA  # noqa: E402
from trussvid import operator as OP  # noqa: E402
from trussvid import pipeline as PL  # noqa: E402

t0 = time.time()
dur = float(sys.argv[1]) if len(sys.argv) > 1 else 1200.0
cfg = PL.ExpCfg(duration=dur)
tr = PL.TruthCache.get(cfg.U10, cfg.duration, cfg.fps, cfg.seed)
res = PL.run(cfg, keep=True, log=lambda *a: None)
ar = res["_arrays"]
Q, Pm, At, Sig = ar["Q"], ar["Pm"], ar["A_true"], ar["Sig_q"]
idx = tr.info["eval_modes"]
T = Pm[:, :At.shape[0]] @ At                   # 真值模态坐标 → 反投影坐标（只取采样带列）
N = Q - tr.q @ T.T                             # 反投影噪声（含时间偏差残差等）
print("结果：", {k: res[k] for k in ("n_freq_1pct", "n_mac90", "mac_per_true_mode", "tau_est_ms")},
      [c["shake_res_urad"] for c in res["cams"]])
print("噪声协方差：理论迹 %.3e  实测迹 %.3e" % (np.trace(Sig), np.trace(np.cov(N.T))))
Cn = np.cov(N.T)
Ci = np.linalg.inv(Cn)
for k in idx:
    v = T[:, k]
    snr = np.std(tr.q[:, k]) * np.sqrt(v @ Ci @ v)     # 最优线性组合下的单帧信噪比
    print(f"  模态{k + 1} f={tr.freq[k]:.3f}  最优单帧 SNR={snr:.3f}")
# Q 空间（白化后）各模态向量间夹角余弦
Lc = np.linalg.cholesky(Cn)
Tw = np.linalg.solve(Lc, T[:, idx])
Tw /= np.linalg.norm(Tw, axis=0, keepdims=True)
print("白化 Q 空间模态向量 |cos|：\n", np.round(np.abs(Tw.T @ Tw), 2))
Qw, Lw = OP.whiten(Q, Sig)
for i_, orders, mc in ((40, range(8, 61, 2), 6), (60, range(10, 81, 2), 5), (80, range(10, 101, 2), 5)):
    md = OMA.identify(Qw, cfg.fps, i=i_, orders=orders, min_count=mc)
    print(f"SSI i={i_} 阶次≤{max(orders)} min_count={mc}:", [(round(m['f'], 3), m['count']) for m in md])
pk = OMA.fdd_peaks(Qw, cfg.fps, n_peaks=12)
print("FDD 峰：", [round(p["f"], 3) for p in pk])
print(f"{time.time() - t0:.0f}s")
