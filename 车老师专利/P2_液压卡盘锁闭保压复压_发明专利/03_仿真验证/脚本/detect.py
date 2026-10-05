# -*- coding: utf-8 -*-
"""静止侧压力传感器 S1 的测量模型与拐点识别算法。

传感器：一阶滞后 τ_s → 按采样频率 fs 取样（随机相位）→ 静态误差（零点 e0、增益 eg、弓形非线性 a_nl）→ 白噪声 → 16 位量化。
拐点识别（本发明的方法，见 07/说明书“拐点识别子步骤”）：
 1) 只在检测窗口 [p_lo, p_hi] 内搜索（p_lo 高于松开侧单向阀先导活塞动作压力，p_hi 低于减压阀上限比例带）；
 2) 窗口内取最大升压速率 s_max（拐点前斜率的估计）；
 3) 自 s_max 所在位置向后，第一个其后连续 n_chk 个升压速率均低于 s_max/r_min 的采样点记为拐点候选 b；
 4) 拐点前直线：b 之前、窗口内、升压速率高于 s_max/r_min 的最多 n_pre 个点最小二乘；不足 2 点时取 1 点加斜率 s_max；
    拐点后直线：t_b+guard 至 t_b+guard+t_post 内（且不超过 p_hi）的点最小二乘，至少 3 点；
 5) 两直线交点 (t_k, p_k) 即拐点；交点时刻限定在 [t_{b-1}, t_b+guard] 内。
"""
import math

import numpy as np


def make_sensor(P, rng, ideal=False):
    """一只压力传感器实例的静态误差参数（0.25%FS 内）。"""
    FS = P["FS"]
    if ideal:
        return dict(e0=0.0, eg=0.0, anl=0.0, noise=0.0, tau=0.0, bits=None, FS=FS)
    return dict(e0=rng.uniform(-0.0015, 0.0015) * FS, eg=rng.uniform(-0.0015, 0.0015),
                anl=rng.uniform(-0.0010, 0.0010) * FS, noise=P["noise"], tau=P["tau_s"], bits=P["adc_bits"], FS=FS)


def sample(E, info, sens, fs, rng, t_end=None, fine=20000.0):
    """按传感器模型对 E 的 p_s(t) 取样。返回 (t_samples, p_samples, p_true_samples)。"""
    I = E.I
    t_end = info["t_off"] if t_end is None else t_end
    tt = np.arange(0.0, t_end, 1.0 / fine)
    ps = E.dense(tt)[I["ps"]]
    if sens["tau"] > 0:
        a = math.exp(-1.0 / (fine * sens["tau"]))
        out = np.empty_like(ps)
        acc = ps[0]
        for k in range(len(ps)):
            acc = a * acc + (1 - a) * ps[k]
            out[k] = acc
        ps_f = out
    else:
        ps_f = ps
    phase = rng.uniform(0, 1.0 / fs)
    ts = np.arange(phase, t_end, 1.0 / fs)
    pf = np.interp(ts, tt, ps_f)
    ptrue = np.interp(ts, tt, ps)
    FS = sens["FS"]
    pm = pf + sens["e0"] + sens["eg"] * pf + sens["anl"] * np.sin(math.pi * np.clip(pf, 0, FS) / FS)
    if sens["noise"] > 0:
        pm = pm + rng.normal(0.0, sens["noise"], len(pm))
    if sens["bits"]:
        q = FS / 2 ** sens["bits"]
        pm = np.round(pm / q) * q
    return ts, pm, ptrue


def knee_P(ts, pm, P, p_red, **kw):
    """按设计基准参数调用 knee()。"""
    lo, hi = window(P, p_red)
    a = dict(r_min=P["slope_ratio_min"], n_pre=P["n_pre"], guard=P["guard"], t_post=P["t_post"])
    a.update(kw)
    return knee(ts, pm, lo, hi, **a)


def knee(ts, pm, p_lo, p_hi, r_min=3.0, n_pre=6, guard=4e-3, t_post=6e-3, chk_t=1.5e-3, ma_t=0.0, strict=True):
    """拐点识别。返回 dict(found, p_k, t_k, s1, s2, n1, n2, reason)。"""
    out = dict(found=False, p_k=float("nan"), t_k=float("nan"), s1=float("nan"), s2=float("nan"), n1=0, n2=0,
               reason="")
    if len(ts) < 5:
        out["reason"] = "采样点不足"
        return out
    dt = ts[1] - ts[0]
    p = pm.copy()
    m = max(1, int(round(ma_t / dt))) if ma_t > 0 else 1
    if m > 1:                                    # 因果滑动平均（两段直线同步滞后，交点压力不变）
        k = np.ones(m) / m
        p = np.convolve(pm, k, mode="full")[:len(pm)]
        p[:m - 1] = pm[:m - 1]
    s = np.diff(p) / dt                          # s[i] 为 i→i+1
    inwin = (p[:-1] >= p_lo) & (p[:-1] <= p_hi)
    if not inwin.any():
        out["reason"] = "压力未进入检测窗口" if p.max() < p_lo else "窗口内无数据"
        return out
    idx = np.where(inwin)[0]
    i0 = idx[0]
    # 拐点前斜率：窗口内（直到首次达到 p_hi）的最大升压速率（取第二大值以抗单点噪声）
    i_hi = np.argmax(p >= p_hi) if (p >= p_hi).any() else len(p) - 1
    seg = s[i0:max(i_hi, i0 + 1)]
    if len(seg) < 2:
        out["reason"] = "窗口内数据过少"
        return out
    order = np.sort(seg)
    s_max = order[-2] if len(order) >= 2 else order[-1]
    if s_max <= 0:
        out["reason"] = "窗口内压力不升"
        return out
    i_smax = i0 + int(np.argmax(seg >= s_max))
    thr = s_max / r_min
    n_chk = max(2, int(round(chk_t / dt)))
    b = None
    for i in range(i_smax, min(i_hi, len(s) - 1) + 1):
        if p[i] < p_lo:
            continue
        win = s[i:i + n_chk]
        if len(win) >= 2 and np.all(win < thr):
            b = i
            break
    if b is None:
        out["reason"] = "窗口内无拐点（锁闭压力高于窗口上限，或升压前已开启）"
        return out
    # 拐点后直线
    t_b = ts[b]
    mpost = (ts >= t_b + guard) & (ts <= t_b + guard + t_post) & (p <= p_hi)
    jj = np.where(mpost)[0]
    # 拐点后段在 p_hi 以下必须至少覆盖 t_post 的一半，否则视为拐点过于接近上限（锁闭压力高于可检测范围）
    if len(jj) < max(3, int(0.5 * t_post / dt)):
        if strict:
            out["reason"] = "拐点后有效数据不足（拐点接近检测上限）"
            out["b"] = int(b)
            return out
        jj = np.arange(b + 1, min(b + 1 + max(3, int(round(t_post / dt))), len(p)))
        jj = jj[p[jj] <= p_hi] if (p[jj] <= p_hi).sum() >= 3 else jj[:3]
        out["reason"] += "拐点后数据不足，已缩短保护段；"
    A2 = np.vstack([ts[jj], np.ones(len(jj))]).T
    s2, a2 = np.linalg.lstsq(A2, p[jj], rcond=None)[0]
    # 拐点前直线：只取两侧相邻区段都处于快速升压的点（排除拐角过渡点）
    fast = 0.5 * s_max
    ii = [i for i in range(b - 1, max(i0, 1) - 1, -1)
          if p[i] >= p_lo and s[i] >= fast and s[i - 1] >= fast][:n_pre]
    ii = sorted(ii)
    if len(ii) >= 2:
        A1 = np.vstack([ts[ii], np.ones(len(ii))]).T
        s1, a1 = np.linalg.lstsq(A1, p[ii], rcond=None)[0]
    else:
        s1 = s_max
        j1 = ii[0] if ii else b - 1
        a1 = p[j1] - s1 * ts[j1]
    if strict and (s2 <= 0 or s1 / max(s2, 1e-9) < r_min):
        out["reason"] = "拐点前后斜率比不足"
        out.update(s1=float(s1), s2=float(s2), b=int(b))
        return out
    if s1 <= s2 * 1.01:
        t_k = t_b
    else:
        t_k = (a2 - a1) / (s1 - s2)
    t_k = min(max(t_k, ts[max(b - 1, 0)]), t_b + guard)
    p_k = a2 + s2 * t_k
    out.update(found=True, p_k=float(p_k), t_k=float(t_k), s1=float(s1), s2=float(s2), n1=len(ii), n2=len(jj),
               reason=out["reason"] or "正常", b=int(b))
    return out


def window(P, p_red):
    return P["p_win_lo"], p_red + P["p_win_hi_rel"]
