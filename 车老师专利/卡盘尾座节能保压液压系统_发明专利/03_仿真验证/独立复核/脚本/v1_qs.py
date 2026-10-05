# -*- coding: utf-8 -*-
"""V1-2 准静态保压闭环模型（独立实现）。
状态：p1、p2、活塞后退量 u。输入：工件伸长 δ(t)、油温 T(t)、泄漏。
方法：压力增量形式 dp_i = β_i(p_i)/V_i·(dV_net)，显式小步长 + 粘滞—滑移线性解析（每步精确求解滑移量）。
控制：推力带 [0.95,1.05]F0（测量值 = p1A1−p2A2，不含传感器误差，确定性），
      M2 越带或 p2<0.5p_pre → 两腔接三通减压阀回复到设定（可选不灵敏区偏置）；M1s 低于下限补油回 F0。
"""
import math
import numpy as np
from v1_common import params, vols, beta_eff, dump, MPa, um, cm3


def simulate(scheme="M2", t_end=600.0, dt=0.25, delta=lambda t: 0.0, dTdt=0.0, leak_mult=1.0,
             Fs=None, db_bias=0.05 * MPa, gap=2.0, ctrl=True, hose_M1s=True, shift=0.0, db2=None, **ov):
    """db_bias：R1 回差（减压—溢流不灵敏区），v1.1 缺省取与 C 相同的假设值 0.05 MPa（v1.0 为 0）；
    db2：R2 回差（缺省同 db_bias）；shift：R1 设定值下移量（0 或 db/2）。"""
    P = params(**ov)
    if Fs is not None:
        P["Fs"] = Fs
    Fc = P["Fc_ratio"] * P["Fs"]
    dual = scheme in ("M2",)
    hose = scheme == "M1s" and hose_M1s
    if hose:
        P["beta0"] = P["beta_hose"]     # 与 C/B 同：含软管锁闭腔取 β=800
    A1, A2, F0 = P["A1"], P["A2"], P["F0"]
    p1s = P["p1set"] if dual else F0 / A1
    p2s = P["ppre"] if dual else 0.0
    p1, p2, u = p1s, p2s, 0.0
    Fw0 = F0
    Vh = P["Vhose"] if hose else 0.0
    a_eff = P["alpha"] - 3 * P["alpha_steel"]
    Ci = P["Cint"] * leak_mult
    T = 0.0
    t_last = -1e9
    n_act, Vtake = 0, 0.0
    ts, Fws, Fhs = [], [], []
    Fpres, Tl, dl = [], [], []      # 动作前液压推力、油温、工件伸长（供 v1_dL 的 ΔL 估算器后处理）
    ev = []
    nstep = int(round(t_end / dt))

    def kh(p1, p2):
        V1, V2 = vols(P, P["x"] - u, hose)
        b1 = beta_eff(P, p1, T, V1, Vh)
        b2 = beta_eff(P, p2, T, V2, Vh) if dual else 0.0
        return b1, b2, V1, V2

    def slide(p1, p2, u, d, hold=False):
        """粘滞—滑移：若 |Fw−Fh|>Fs 则滑移到 ±Fc；hold=True 时两腔压力被减压阀保持（kh=0）。"""
        for _ in range(3):  # β 非线性，迭代 3 次
            Fh = p1 * A1 - p2 * A2
            Fw = Fw0 + P["km"] * (d - u)
            g = Fw - Fh
            if abs(g) <= P["Fs"] + 1e-9:
                break
            b1, b2, V1, V2 = kh(p1, p2)
            k = 0.0 if hold else (b1 * A1 ** 2 / V1 + b2 * A2 ** 2 / V2)
            du = (g - math.copysign(Fc, g)) / (k + P["km"])
            if not hold:
                p1 += b1 * A1 * du / V1
                p2 -= b2 * A2 * du / V2 if dual else 0.0
            u += du
        return p1, p2, u

    for i in range(nstep + 1):
        t = i * dt
        d = delta(t)
        if i > 0:
            b1, b2, V1, V2 = kh(p1, p2)
            dT = dTdt * dt
            T += dT
            q = Ci * (p1 - p2) if dual else Ci * p1          # 1→2（单腔为 1→油箱）
            qs1 = P["Cseat"] * max(p1, 0)
            qs2 = P["Cseat"] * max(p2, 0) if dual else 0.0
            p1 += b1 / V1 * (a_eff * V1 * dT - (q + qs1) * dt)
            if dual:
                p2 += b2 / V2 * (a_eff * V2 * dT + (q - qs2) * dt)
            p2 = max(p2, -0.09 * MPa) if dual else 0.0
            p1, p2, u = slide(p1, p2, u, d)
        Fh = p1 * A1 - p2 * A2
        Fw = Fw0 + P["km"] * (d - u)
        Fpre = Fh
        act = False
        if ctrl and t - t_last >= gap:
            if scheme == "M2" and (Fh > (1 + P["band"]) * F0 or Fh < (1 - P["band"]) * F0 or p2 < 0.5 * P["ppre"]):
                act = True
            if scheme == "M1s" and Fh < (1 - P["band"]) * F0:
                act = True
        if act:
            b1, b2, V1, V2 = kh(p1, p2)
            # v1.1：两只三通减压阀均按“回差窗口”建模——低于设定补到设定，高于设定+回差溢流到设定+回差，窗口内不变
            # （v1.0 只给 R1 加回差、且不论方向都置到端点，R2 恒回到 p_pre，见报告 3.4）
            def win(p, ps, db):
                return ps if p < ps else (ps + db if p > ps + db else p)
            q1n = win(p1, p1s - shift, db_bias) if scheme == "M2" else p1s
            q2n = win(p2, p2s, db_bias if db2 is None else db2) if dual else 0.0
            Vtake += max(0.0, (q1n - p1) * V1 / b1) + (max(0.0, (q2n - p2) * V2 / b2) if dual else 0.0)
            p1, p2 = q1n, q2n
            p1, p2, u = slide(p1, p2, u, d, hold=True)   # 阀开期间压力被保持，活塞滑移到 ±Fc
            n_act += 1
            t_last = t
            ev.append(t)
            Fh = p1 * A1 - p2 * A2
            Fw = Fw0 + P["km"] * (d - u)
        ts.append(t); Fws.append(Fw); Fhs.append(Fh)
        Fpres.append(Fpre); Tl.append(T); dl.append(d / um)
    Fws = np.array(Fws)
    return {"t": ts, "Fw": Fws.tolist(), "Fh": Fhs, "Fh_pre": Fpres, "T": Tl, "d_um": dl, "max_pos%": 100 * (Fws.max() / F0 - 1),
            "max_neg%": 100 * (Fws.min() / F0 - 1), "n_act": n_act, "events": ev, "V_take_cm3": Vtake / cm3}


def growth(dmax_um, tau):
    return lambda t: dmax_um * um * (1 - math.exp(-t / tau))


def ramp(dmax_um, t_r):
    return lambda t: dmax_um * um * min(t / t_r, 1.0)


if __name__ == "__main__":
    R = {}
    base = dict(air=0.005)    # 与 C 同：未溶解空气 0.5%
    sc = {
        "C1 伸长57.5um τ5min": dict(delta=growth(57.5, 300), leak_mult=0.0),
        "C2 伸长138um τ10min": dict(delta=growth(138, 600), leak_mult=0.0),
        "C3 油温+0.2K/min": dict(dTdt=0.2 / 60, leak_mult=0.0),
        "C4 油温-0.2K/min": dict(dTdt=-0.2 / 60, leak_mult=0.0),
        "C5 内泄漏×4": dict(leak_mult=4),
        "C6 综合": dict(delta=growth(57.5, 300), dTdt=0.1 / 60),
        "C7 1h 油温-5K/h": dict(dTdt=-5 / 3600, t_end=3600, dt=1.0),
    }  # 与 C 一致：C1~C4 内泄漏取 0，C5~C7 取 ×1/×4
    for k, a in sc.items():
        R[k] = {}
        for s in ("M1s", "M2"):
            r = simulate(s, **a, **base)
            rb = simulate(s, hose_M1s=False, **a, **base) if s == "M1s" else None
            if rb: R[k]["M1s_阀块直装β1200(=C实际所用)"] = {"max_pos%": rb["max_pos%"], "max_neg%": rb["max_neg%"], "n_act": rb["n_act"]}
            R[k][s] = {kk: r[kk] for kk in ("max_pos%", "max_neg%", "n_act", "V_take_cm3")}
            if s == "M2":
                R[k][s]["events_first"] = r["events"][:5]
        print(k, R[k])
    # 15 µm 工件热伸长（斜坡 60 s 与准阶跃 1 s），无控制动作时的推力增量，以及有无摩擦
    R["15um"] = {}
    for s in ("M1s", "M2"):
      for hb in (True, False):
        if s == "M2" and not hb: continue
        for Fs in (0.0, 150.0):
            for lab, ov in (("理想β", {}), ("空气0.5%", base)):
                r = simulate(s, hose_M1s=hb, t_end=120, dt=0.1, delta=ramp(15, 60), Fs=Fs, ctrl=False, leak_mult=0.0, **ov)
                R["15um"][f"{s}{'' if hb or s=='M2' else '_阀块直装'}_Fs{int(Fs)}_{lab}"] = {"ΔF_N": r["Fw"][-1] - 6000, "Δ%": r["Fw"][-1] / 60 - 100,
                                                       "测量ΔFh_N": r["Fh"][-1] - 6000}
    print(R["15um"])
    # 泄漏导致的补压间隔（恒温、无伸长）
    R["泄漏补压间隔"] = {}
    for lm in (0.1, 1, 4):
        for lab, ov in (("理想β", {}), ("空气0.5%", base)):
            r = simulate("M2", t_end=3600 if lm >= 1 else 36000, dt=1.0 if lm >= 1 else 5.0, leak_mult=lm, **ov)
            ev = r["events"]
            R["泄漏补压间隔"][f"×{lm}_{lab}"] = {"首次s": ev[0] if ev else None,
                                             "平均间隔s": float(np.mean(np.diff(ev))) if len(ev) > 1 else None,
                                             "次数": len(ev)}
    print(R["泄漏补压间隔"])
    # 敏感性（不保守假设）
    S = {}
    for lab, ov in (("基准", base), ("空气1%", dict(air=0.01)), ("空气2%", dict(air=0.02)),
                    ("组合非理想(空气1%+缸筒+K'11)", dict(air=0.01, wall=True, Kp=11.0)),
                    ("Fs=300", dict(air=0.005, Fs=300.0)),
                    ("Fs=300+空气1%", dict(air=0.01, Fs=300.0)),
                    ("座阀泄漏1e-2", dict(air=0.005, Cseat=1e-2 * cm3 / 60 / 1e6)),
                    ("座阀泄漏0.1", dict(air=0.005, Cseat=0.1 * cm3 / 60 / 1e6)),
                    ("减压阀回差0.1MPa(两阀)", dict(air=0.005, db_bias=0.1 * MPa)),
                    ("理想减压阀(回差0)", dict(air=0.005, db_bias=0.0)),
                    ("低F0=2000", dict(air=0.005, F0=2000))):
        row = {}
        for cn in ("C3 油温+0.2K/min", "C6 综合", "C5 内泄漏×4"):
            a = dict(sc[cn]); a.update(ov)
            if "Fs" in ov: a["Fs"] = ov["Fs"]
            r2 = simulate("M2", **a)
            r1 = simulate("M1s", **a)
            row[cn] = {"M2_max_pos%": r2["max_pos%"], "M2_max_neg%": r2["max_neg%"], "M2_n": r2["n_act"],
                       "M1s_max_pos%": r1["max_pos%"]}
        S[lab] = row
        print(lab, row)
    R["敏感性"] = S
    # 步长收敛
    R["步长收敛_C6_M2"] = {dt: simulate("M2", dt=dt, **sc["C6 综合"], **base)["max_pos%"] for dt in (1.0, 0.25, 0.05)}
    print(R["步长收敛_C6_M2"])
    dump("v1_qs", R)
