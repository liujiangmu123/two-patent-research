# -*- coding: utf-8 -*-
"""P2 仿真主程序。用法：python sim_all.py [stage ...]
stage：validate curves supply sens mc cycle（缺省全部）。结果写 数据/<stage>.json。
"""
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from params import load, MPa, cm3, Lmin, kPa, DATA, SEED, caps, c_omega, p_min_n, n_prog, G_rot, mu_T
from event_model import Event
from detect import make_sensor, sample, knee_P, knee, window
from sim_lib import (measure, calibrate, estimate, nominal_cal, q_sched, visc_ratio, Hold, grip, p_equiv, C_LINE_NOM)

NPROC = int(os.environ.get("P2_NPROC", str(min(16, os.cpu_count() or 4))))   # 与其他子任务共用机器，缺省 16 进程


def dump(name, obj):
    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=conv)
    print("写出", name + ".json", flush=True)


def kpa(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x / 1e3, 3)


# ================================================================ 1 求解器与模型校核
def st_validate(P):
    out = {}
    rng = np.random.default_rng(SEED)
    ideal = make_sensor(P, rng, ideal=True)
    # 1a 解析校核：无空气、无泄漏、油道阻力极小、无冲击，刚性与弹性机构两种。
    #   原做法（2026-10-01 13:43）在 [t_k−3 ms, t_k−0.4 ms] 上拟合拐点前斜率，得 383 MPa/s，比 Q/C_line=769 MPa/s 低 50%。
    #   续做排查：两侧容腔口径一致（均为 13 cm3/1200 MPa），流量口径一致（0.5 L/min）；偏差来自
    #   (1) 拟合窗口伸入松开侧先导活塞动作平台段（0.35~0.45 MPa 停留约 15 ms），
    #   (2) 先导活塞按一阶滞后跟随（τ=2 ms），快速升压段（约 1.5 ms）内仍在吸油，解析式未计这部分流量。
    #   现改为：拟合段只取 0.6 MPa 至拐点真值−0.05 MPa 的纯升压段；先导活塞排量置零时与 Q/C_line 比较（求解器校核），
    #   保留先导活塞时与 (Q−Q_pp)/C_line 比较（Q_pp 取模型先导活塞吸油的段内平均值），并给出先导活塞对拐点前斜率的影响。
    Cl, Co, Cm = 13 * cm3 / P["beta_m"], P["V_c"] / P["beta_lock"], P["A2"] ** 2 / P["k_mech"]
    from scipy.optimize import brentq
    rows = []
    for rigid in (True, False):
        for pilot in (False, True):
            E = Event(P, dict(p_c0=1.5 * MPa, air=0.0, leak_mult=0.0, R_path_mult=0.01, surge=0.0, rigid=rigid,
                              Q_m=0.5 * Lmin, p_red=2.6 * MPa, t_max=0.6, p_u0=0.0, V_pp=P["V_pp"] if pilot else 0.0))
            t, Y, info = E.run(rtol=1e-8, max_step=5e-5)
            kt = E.knee_truth(t, Y)
            tf = np.linspace(max(kt[0] - 0.03, 0.0), kt[0], 30001)
            D1 = E.dense(tf)
            psf = D1[E.I["ps"]]
            m = (psf >= 0.6 * MPa) & (psf <= kt[1] - 0.05 * MPa)
            s1 = np.polyfit(tf[m], psf[m], 1)[0]
            q_pp = float(np.mean(np.gradient(D1[E.I["ypp"]], tf)[m])) * E.c["V_pp"]
            s1a0 = 0.5 * Lmin / Cl
            s1a = (0.5 * Lmin - q_pp) / Cl
            tt2 = np.linspace(kt[0] + 3e-3, kt[0] + 7e-3, 60) if rigid else np.linspace(kt[0] + 15e-3, kt[0] + 35e-3, 80)
            D2 = E.dense(tt2)
            s2 = np.polyfit(tt2, D2[E.I["ps"]], 1)[0]
            s2a = 0.5 * Lmin / (Cl + Co + (0 if rigid else Cm))
            # 稳态开启压差解析：Δp·A = k(x0+x) + 液动力，Q = cv_k·x·sqrt(Δp)
            Q = 0.5 * Lmin - Cl * s2
            ff = 2 * P["Cd"] * math.pi * P["d_seat"] * math.sin(P["half_cone"]) * math.cos(P["half_cone"])

            def g(dp):
                x = Q / (E.cv_k * dp / math.sqrt(dp + 5e3))
                return dp * P["A_seat"] - P["k_spr"] * (E.x0v + x) - ff * x * dp
            dpa = brentq(g, P["p_cr"] * 0.9, P["p_cr"] * 3)
            dpm = float(np.mean(D2[E.I["pr"]] - D2[E.I["pc"]]))
            rows.append(dict(机构="刚性" if rigid else "弹性 40 kN/mm", 先导活塞="计入（0.15 cm3，τ=2 ms）" if pilot else "置零",
                             拟合段_MPa=[0.6, round((kt[1] - 0.05 * MPa) / 1e6, 4)], 拟合段时长_ms=float((tf[m][-1] - tf[m][0]) * 1e3),
                             拐点前斜率_模型_MPa_s=s1 / 1e6, 拐点前斜率_解析_Q除C_MPa_s=s1a0 / 1e6,
                             拐点前斜率_解析_扣先导吸油_MPa_s=s1a / 1e6, 先导活塞段内平均吸油_cm3_s=q_pp / cm3,
                             相对误差1=s1 / s1a - 1, 相对Q除C=s1 / s1a0 - 1,
                             拐点后斜率_模型=s2 / 1e6, 拐点后斜率_解析=s2a / 1e6, 相对误差2=s2 / s2a - 1,
                             开启后阀口压差_模型_kPa=dpm / 1e3, 开启后阀口压差_解析_kPa=dpa / 1e3, 相对误差3=dpm / dpa - 1))
    out["解析校核"] = rows
    out["解析校核_说明"] = ("原 −50% 偏差的原因：拟合窗口伸入先导活塞动作平台段，且先导活塞一阶滞后使快速升压段仍吸油；"
                       "容腔与流量口径无误。改用纯升压段并扣除先导活塞吸油后，模型与解析式一致（见相对误差1）。")
    # 1b 体积守恒（断电前时刻，单向阀上游：流入−溢流−泄漏−单向阀流量−先导活塞排量 = 节点 s、r 的压缩量）
    from params import beta_eff
    from scipy.integrate import quad
    E = Event(P, dict(p_c0=1.6 * MPa))
    t, Y, info = E.run(rtol=1e-8, max_step=5e-5)
    I = E.I
    y = E.dense(np.array([info["t_off"] - 1e-6]))[:, 0]
    comp = lambda V, p: V * quad(lambda q: 1.0 / beta_eff(q, P["beta_m"], P["air_frac"]), 0.0, p)[0]
    lhs = y[I["Vin"]] - y[I["Vrel"]] - y[I["Vleak"]] - y[I["Vcv"]] - E.c["V_pp"] * y[I["ypp"]]
    rhs = comp(E.V_s, y[I["ps"]]) + comp(E.V_r, y[I["pr"]])
    out["体积守恒"] = dict(说明="断电前时刻，单向阀上游：流入−溢流−泄漏−单向阀流量−先导活塞排量 与 节点 s、r 压缩量比较",
                        流入_cm3=y[I["Vin"]] / cm3, 泄漏_cm3=y[I["Vleak"]] / cm3, 单向阀_cm3=y[I["Vcv"]] / cm3,
                        左端_cm3=lhs / cm3, 压缩量_cm3=rhs / cm3, 相对差=(lhs - rhs) / rhs)
    # 1c 积分容差与最大步长收敛（理想传感器、固定相位）
    rng2 = np.random.default_rng(1)
    conv = []
    for rtol, ms in ((1e-5, 2e-4), (1e-6, 2e-4), (1e-7, 1e-4), (1e-8, 5e-5)):
        E = Event(P, dict(p_c0=1.6 * MPa))
        t, Y, info = E.run(rtol=rtol, max_step=ms)
        ts, pm, _ = sample(E, info, ideal, P["fs"], np.random.default_rng(7))
        k = knee_P(ts, pm, P, E.c["p_red"])
        conv.append(dict(rtol=rtol, max_step=ms, p_k_MPa=k["p_k"] / 1e6, p_c_end_MPa=info["p_c_end"] / 1e6,
                         V_leak_cm3=info["V_leak"] / cm3))
    ref = conv[-1]
    for r in conv:
        r["p_k差_kPa"] = (r["p_k_MPa"] - ref["p_k_MPa"]) * 1e3
    out["容差收敛"] = conv
    # 1d 离心修正
    cen = []
    for n in (0, 1500, 3000, 4000):
        vals = []
        for rep in range(3):
            E = Event(P, dict(p_c0=1.6 * MPa, n_rpm=n))
            t, Y, info = E.run()
            ts, pm, _ = sample(E, info, ideal, P["fs"], np.random.default_rng(10 + rep))
            k = knee_P(ts, pm, P, E.c["p_red"])
            vals.append(k["p_k"])
        cen.append(dict(n=n, p_k_MPa=float(np.mean(vals)) / 1e6, 理论离心修正_kPa=c_omega(P) * n * n / 1e3))
    for r in cen:
        r["拐点下降_kPa"] = (cen[0]["p_k_MPa"] - r["p_k_MPa"]) * 1e3
    out["离心修正"] = cen
    # 1e 软管分段收敛（阀板布置）
    segs = []
    for N in (4, 6, 10):
        E = Event(P, dict(layout="plate", N=N, p_c0=1.6 * MPa))
        t, Y, info = E.run()
        kt = E.knee_truth(t, Y)
        tt = np.arange(kt[0] - 0.02, kt[0], 2e-5)
        ps = E.dense(tt)[E.I["ps"]]
        ac = ps - np.polyval(np.polyfit(tt, ps, 2), tt)
        f = np.fft.rfftfreq(len(ac), 2e-5)
        F = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
        fpk = float(f[np.argmax(F[1:]) + 1])
        segs.append(dict(N=N, 拐点真值_ps_MPa=kt[1] / 1e6, 拐点前主振荡频率_Hz=fpk, p_c_end_MPa=info["p_c_end"] / 1e6))
    c_w = math.sqrt(P["beta_h"] / P["rho"])
    out["软管分段"] = dict(结果=segs, 波速_m_s=c_w, 四分之一波长频率_Hz=c_w / (4 * P["L_hose"]),
                       半波长频率_Hz=c_w / (2 * P["L_hose"]))
    out["参数"] = dict(C_line=Cl, C_oil=Co, C_mech=Cm, 斜率比_弹性=(Cl + Co + Cm) / Cl, 斜率比_刚性=(Cl + Co) / Cl,
                     c_omega_Pa_per_rpm2=c_omega(P))
    dump("validate", out)


# ================================================================ 2 典型曲线
def st_curves(P):
    rng = np.random.default_rng(SEED + 1)
    sens = make_sensor(P, rng)
    out = {}
    cases = [("p140", dict(p_c0=1.40 * MPa)), ("p160", dict(p_c0=1.60 * MPa)), ("p180", dict(p_c0=1.80 * MPa)),
             ("p200", dict(p_c0=2.00 * MPa)), ("rigid160", dict(p_c0=1.60 * MPa, rigid=True)),
             ("plate160", dict(p_c0=1.60 * MPa, layout="plate")), ("chatter160", dict(p_c0=1.60 * MPa, c_pop=6.0)),
             ("n3000_160", dict(p_c0=1.60 * MPa, n_rpm=3000))]
    for name, cfg in cases:
        cfg = dict(cfg, Q_m=q_sched(P, 40.0))
        r = measure(P, cfg, sens, rng, keep=True)
        E, info = r["E"], r["info"]
        tt = np.arange(0, info["t_off"] + 0.02, 2e-4)
        D = E.dense(tt)
        kt = E.knee_truth(r["t"], r["Y"])
        out[name] = dict(cfg={k: v for k, v in r["cfg"].items() if isinstance(v, (int, float, str, bool))},
                         t=tt.tolist(), ps=(D[E.I["ps"]] / 1e6).tolist(), pc=(D[E.I["pc"]] / 1e6).tolist(),
                         pu=(D[E.I["pu"]] / 1e6).tolist(), ts=r["ts"].tolist(), pm=(r["pm"] / 1e6).tolist(),
                         knee=r["k"], knee_true=kt, p_red=r["p_red"] / 1e6, info=info, p_c0=r["p_c0"] / 1e6)
    dump("curves", out)


# ================================================================ 3 供油方式与布置对比
def _supply_job(args):
    P, name, cfg, seed = args
    rng = np.random.default_rng(seed)
    sens = make_sensor(P, rng)
    res = []
    for pc in (1.40, 1.60, 1.80):
        for rep in range(4):
            r = measure(P, dict(cfg, p_c0=pc * MPa, p_cr_sigma=P["sig_cr"]), sens, rng, keep=(rep == 0 and pc == 1.6))
            k = r["k"]
            row = dict(pc=pc, found=k["found"], off_kPa=kpa(k["p_k"] - pc * MPa) if k["found"] else None,
                       s1=k["s1"] / 1e6 if k["found"] else None, s2=k["s2"] / 1e6 if k["found"] else None, reason=k["reason"])
            if "E" in r:
                E = r["E"]
                kt = E.knee_truth(r["t"], r["Y"])
                if kt:
                    t0 = kt[0]
                    tt = np.linspace(t0 - 2e-3, t0 - 0.3e-3, 30)
                    tt2 = np.linspace(t0 + 5e-3, t0 + 10e-3, 30)
                    s1t = np.polyfit(tt, E.dense(tt)[E.I["ps"]], 1)[0]
                    s2t = np.polyfit(tt2, E.dense(tt2)[E.I["ps"]], 1)[0]
                    row.update(斜率比_真值=s1t / s2t if s2t > 0 else None, s1t=s1t / 1e6, s2t=s2t / 1e6)
            res.append(row)
    offs = np.array([x["off_kPa"] for x in res if x["off_kPa"] is not None])
    succ = np.mean([x["found"] for x in res])
    sr = [x.get("斜率比_真值") for x in res if x.get("斜率比_真值")]
    return name, dict(cfg={k: v for k, v in cfg.items() if isinstance(v, (int, float, str, bool))}, 识别率=float(succ),
                      偏置均值_kPa=float(offs.mean()) if len(offs) else None,
                      偏置标准差_kPa=float(offs.std(ddof=1)) if len(offs) > 1 else None,
                      偏置极差_kPa=float(offs.max() - offs.min()) if len(offs) else None,
                      斜率比_真值=sr[0] if sr else None, 明细=res)


def st_supply(P):
    A_or = P["Q_net_target"] / (P["Cd"] * math.sqrt(2 * (P["p_acc"] - 2.0 * MPa) / P["rho"]))
    A_or = (q_sched(P, 40.0)) / (P["Cd"] * math.sqrt(2 * (P["p_acc"] - 2.0 * MPa) / P["rho"]))
    jobs = [
        ("A 调速阀限流（本发明，检测阀块在回转接头处）", dict(Q_m=q_sched(P, 40.0))),
        ("B 固定节流孔自蓄能器供油", dict(fcv_mode="orifice", A_orif=A_or)),
        ("C 比例减压阀斜坡直供（20 MPa/s）", dict(fcv_mode="ramp", ramp_rate=20 * MPa, ramp_p0=0.3 * MPa)),
        ("D 比例减压阀斜坡+串联节流孔（20 MPa/s）", dict(fcv_mode="ramp_orif", ramp_rate=20 * MPa, ramp_p0=0.3 * MPa, A_orif=A_or)),
        ("E 调速阀装在阀板、经软管供油", dict(layout="plate", Q_m=q_sched(P, 40.0))),
        ("F 定量泵直供（不限流，5.2 L/min）", dict(Q_m=5.8 * 0.9 * Lmin)),
    ]
    args = [(P, n, c, SEED + 100 + i) for i, (n, c) in enumerate(jobs)]
    with ProcessPoolExecutor(min(NPROC, len(args))) as ex:
        res = dict(ex.map(_supply_job, args))
    res["_说明"] = "每种方式 3 个锁闭压力×4 次（随机采样相位、噪声、开启压差离散），真实传感器 2 kHz；偏置=拐点压力−真实锁闭压力；偏置的离散度即该方式经一次标定后的识别误差下限"
    res["_节流孔面积_m2"] = A_or
    dump("supply", res)


# ================================================================ 4 单因素敏感性
def _sens_job(args):
    P, fac, lvl, cfg_test, cfg_cal, seed, est_kw = args
    rng = np.random.default_rng(seed)
    sens = make_sensor(P, rng)
    mach = dict(cfg_cal)
    cal = calibrate(P, mach, sens, rng, mode="T", fs=cfg_test.get("_fs"))
    errs, fails = [], 0
    for pc in (1.35, 1.55, 1.75, 1.85):
        for rep in range(3):
            T = cfg_test.get("T", 40.0)
            Tm = T + rng.uniform(-P["T_err"], P["T_err"])
            c = {k: v for k, v in cfg_test.items() if not k.startswith("_")}
            c.setdefault("Q_m", q_sched(P, Tm))
            c.update(p_c0=pc * MPa, p_cr_sigma=P["sig_cr"])
            r = measure(P, c, dict(sens, e0=sens["e0"] + cfg_test.get("_drift", 0.0), noise=cfg_test.get("_noise", sens["noise"])),
                        rng, fs=cfg_test.get("_fs"))
            ph = estimate(P, r["k"], Tm, c.get("n_rpm", 0.0), cal, **est_kw)
            if ph is None:
                fails += 1
                continue
            errs.append((ph - pc * MPa) / 1e3)
    e = np.array(errs)
    return fac, lvl, dict(n=len(e), 失败=fails, 平均误差_kPa=float(e.mean()) if len(e) else None,
                          标准差_kPa=float(e.std(ddof=1)) if len(e) > 1 else None,
                          最大绝对误差_kPa=float(np.abs(e).max()) if len(e) else None, 标定残差_kPa=kpa(cal["rms_res"]))


def st_sens(P):
    J = []
    s = SEED + 300
    def add(fac, lvl, test, cal=None, est=None):
        nonlocal s
        s += 1
        J.append((P, fac, lvl, test, cal or {}, s, est or {}))
    add("基准", "额定", {})
    for fs in (500, 1000, 2000, 5000):
        add("采样频率_Hz", fs, {"_fs": fs})
    for T in (20, 30, 50, 60):
        add("油温_degC（限流按油温调度）", T, {"T": float(T)})
    for T in (20, 60):
        add("油温_degC（限流固定 1.0 L/min）", T, {"T": float(T), "Q_m": P["Q_m"]}, {"Q_m": P["Q_m"]})
    for lm in (0.5, 0.8, 1.25, 1.6, 2.0):
        add("回转接头泄漏相对标定时倍数", lm, {"leak_mult": lm})
    for n in (1500, 3000, 4000):
        add("主轴转速_rpm（含离心修正）", n, {"n_rpm": float(n)})
        add("主轴转速_rpm（不作离心修正）", n, {"n_rpm": float(n)}, est={"centrifugal": False})
    add("离心修正系数误差", "+10%", {"n_rpm": 3000.0}, est={"cw_err": 0.10})
    for km in (15, 100, 165):
        add("机构刚度_kN_mm", km, {"k_mech": km * 1e6}, {"k_mech": km * 1e6})
    add("机构刚度_kN_mm", "刚性", {"rigid": True}, {"rigid": True})
    for cp in (6, 12, 40):
        add("阀芯阻尼_N_s_m", cp, {"c_pop": float(cp)}, {"c_pop": float(cp)})
    for pcr in (0.03, 0.2, 0.3):
        add("开启压差_MPa（已标定）", pcr, {"p_cr": pcr * MPa}, {"p_cr": pcr * MPa})
    for vj in (8, 25, 50):
        add("检测容腔_cm3", vj, {"V_joint": vj * cm3}, {"V_joint": vj * cm3})
    for qn in (0.25, 1.0):
        P2 = dict(P, Q_net_target=qn * Lmin)
        s += 1
        J.append((P2, "目标净流量_L_min", qn, {}, {}, s, {}))
    for nz in (0.0002, 0.001, 0.002):
        add("传感器噪声_FS", nz, {"_noise": nz * P["FS"]})
    add("传感器标定后零漂_FS", 0.0005, {"_drift": 0.0005 * P["FS"]})
    for ppo in (0.2, 0.5, 0.6):
        add("先导开启压力_MPa", ppo, {"p_po": ppo * MPa}, {"p_po": ppo * MPa})
    add("调速阀流量偏差", "+5%", {"Q_m_err": 0.05})
    add("调速阀流量偏差", "-5%", {"Q_m_err": -0.05})
    add("内泄漏使松开腔初压", "0.3 MPa", {"p_u0": 0.3 * MPa})
    t0 = time.time()
    with ProcessPoolExecutor(NPROC) as ex:
        res = list(ex.map(_sens_job, J))
    out = {}
    for fac, lvl, r in res:
        out.setdefault(fac, {})[str(lvl)] = r
    out["_说明"] = ("每组：按该组机器参数做一次调试标定（主轴静止、30/50 ℃、3 个已知压力），再在该组工况下测 4 个锁闭压力×3 次。"
                  "误差=估计值−真实锁闭压力（面积平均）。传感器为随机静态误差实例+0.05%FS 噪声，采样 2 kHz（除另注）。")
    out["_用时_s"] = time.time() - t0
    dump("sens", out)


# ================================================================ 5 蒙特卡洛
def _mc_job(args):
    P, seed = args
    rng = np.random.default_rng(seed)
    mach = dict(p_cr=P["p_cr"] * rng.uniform(0.8, 1.2), k_mech=math.exp(rng.uniform(math.log(20e6), math.log(100e6))),
                c_pop=rng.uniform(12, 40), V_joint=rng.uniform(10, 20) * cm3, p_po=rng.uniform(0.25, 0.5) * MPa,
                R_path_mult=rng.uniform(0.7, 1.4), leak_mult=math.exp(rng.uniform(math.log(0.7), math.log(1.4))))
    sens = make_sensor(P, rng)
    cal = calibrate(P, mach, sens, rng, mode="T")
    nom = nominal_cal(P)
    rows = []
    for j in range(5):
        T = rng.uniform(20, 60)
        Tm = T + rng.uniform(-P["T_err"], P["T_err"])
        n = rng.uniform(0, 3000)
        pc = rng.uniform(1.3, 1.88)
        drift = math.exp(rng.uniform(math.log(0.8), math.log(1.25)))
        c = dict(mach, T=T, n_rpm=n, p_c0=pc * MPa, p_cr_sigma=P["sig_cr"], leak_mult=mach["leak_mult"] * drift,
                 Q_m=q_sched(P, Tm), Q_m_err=rng.uniform(-0.03, 0.03))
        sens_t = dict(sens, e0=sens["e0"] + rng.uniform(-0.0005, 0.0005) * P["FS"])
        r = measure(P, c, sens_t, rng)
        k = r["k"]
        cw = rng.uniform(-0.1, 0.1)
        e_main = estimate(P, k, Tm, n, cal, cw_err=cw)
        e_noc = estimate(P, k, Tm, n, cal, centrifugal=False)
        e_nom = estimate(P, k, Tm, n, nom, cw_err=cw)
        rows.append(dict(T=T, n=n, pc=pc, drift=drift, found=k["found"], reason=k["reason"],
                         err_main=None if e_main is None else (e_main - pc * MPa) / 1e3,
                         err_noc=None if e_noc is None else (e_noc - pc * MPa) / 1e3,
                         err_nom=None if e_nom is None else (e_nom - pc * MPa) / 1e3,
                         s2=k["s2"] / 1e6 if k["found"] else None))
    return dict(mach={k: (v if not isinstance(v, float) else round(v, 6)) for k, v in mach.items()}, cal=cal["beta"],
                cal_res=cal["rms_res"], rows=rows)


def st_mc(P, N=None):
    N = N or int(os.environ.get("P2_MC_N", "160"))
    t0 = time.time()
    with ProcessPoolExecutor(NPROC) as ex:
        res = list(ex.map(_mc_job, [(P, SEED + 1000 + i) for i in range(N)]))
    rows = [r for m in res for r in m["rows"]]

    def stat(key):
        e = np.array([r[key] for r in rows if r[key] is not None])
        a = np.abs(e)
        bs = [np.percentile(np.abs(np.random.default_rng(i).choice(e, len(e))), 95) for i in range(500)]
        return dict(n=len(e), 平均_kPa=float(e.mean()), 标准差_kPa=float(e.std(ddof=1)), P95绝对_kPa=float(np.percentile(a, 95)),
                    P99绝对_kPa=float(np.percentile(a, 99)), 最大绝对_kPa=float(a.max()),
                    P95_95置信区间_kPa=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                    相对p_set_P95_pct=float(np.percentile(a, 95) / (P["p_set"] / 1e3) * 100))
    found = np.mean([r["found"] for r in rows])
    reasons = {}
    for r in rows:
        if not r["found"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    # 收敛：前一半与全部
    half = rows[: len(rows) // 2]
    e_half = np.abs([r["err_main"] for r in half if r["err_main"] is not None])
    out = dict(N_机器=N, N_事件=len(rows), 识别率=float(found), 未识别原因=reasons,
               调试标定后=stat("err_main"), 不作离心修正=stat("err_noc"), 未标定_取设计偏置=stat("err_nom"),
               收敛_前一半P95_kPa=float(np.percentile(e_half, 95)),
               随机范围=dict(开启压差="设计值×U(0.8,1.2)", 机构刚度="对数均匀 20~100 kN/mm", 阀芯阻尼="U(12,40) N·s/m",
                         检测容腔="U(10,20) cm3", 先导开启="U(0.25,0.5) MPa", 油道阻力="×U(0.7,1.4)",
                         泄漏="标定时×对数U(0.7,1.4)，使用时再×对数U(0.8,1.25)", 油温="U(20,60) ℃（传感器 ±0.5 K）",
                         转速="U(0,3000) r/min（离心修正系数误差 ±10%）", 锁闭压力="U(1.30,1.88) MPa",
                         传感器="0.25%FS 内随机静态误差+0.05%FS 噪声，标定后零漂 ±0.05%FS", 调速阀="±3%"),
               用时_s=time.time() - t0, 明细=rows)
    dump("mc", out)


# ================================================================ 6 保压周期（秒级）
def run_cycle(P, scheme, scen, seed=SEED + 2000, t_end=None, prog=None, record=True):
    """scheme: M0 持续带压 / M1 锁闭+定时复压 / M2 本发明 / M3 旋转侧无线测压+阈值复压。"""
    rng = np.random.default_rng(seed)
    t_end = t_end or P["t_hold_cycle"]
    Pp = dict(P, n_prog=prog) if prog else P
    H = Hold(P, C_int=P["C_int"] * scen.get("C_int_mult", 1.0), k_mech=scen.get("k_mech", P["k_mech"]))
    T0 = scen.get("T0", 40.0)
    dTdt = scen.get("dTdt", P["dTdt_nom"])
    p_fill_nom = None
    # 夹紧：以 M2 同样的检测上限把夹紧腔充到 p_fill
    E0 = Event(P, dict(p_c0=1.2 * MPa, Q_m=q_sched(P, T0), T=T0))
    _, _, inf0 = E0.run()
    p_fill_nom = inf0["p_c_end"]
    H.set_state(p_fill_nom, 0.0, T=0.0)
    sens = make_sensor(P, rng)
    mach = dict()
    cal = calibrate(P, mach, sens, rng, mode="T") if scheme == "M2" else None
    G40 = P["G_rot40"] * scen.get("leak_mult", 1.0)
    log = dict(t=[], pc=[], pu=[], peq=[], pmin=[], n=[], est=[], events=[])
    V_leak = V_acc = 0.0
    t_press = 0.0
    heat = 0.0
    n_ev = 0
    alarms = []
    # M2 调度状态
    last_t, last_fill = 0.0, p_fill_nom
    r_hat = None
    r_up = 1.0e3                     # 先验压降速率上限 1 kPa/s
    next_t = 0.0
    dead = 0.12 * MPa                # 拐点可见下限至充液压力的间隔（由 curves 阶段结果确定的保守值）
    if scheme == "M1":
        next_t = 60.0
    elif scheme == "M3":
        next_t = 1e9
    elif scheme == "M2":
        next_t = min(P["T_max"], max(P["T_min"], (p_fill_nom - p_min_n(P, n_prog(Pp, 0.0)) - P["m_trig"]) / r_up))
    dt = 1.0
    t = 0.0
    viol = 0.0
    min_margin = 1e9
    est_err = []
    while t <= t_end + 1e-9:
        n = n_prog(Pp, t)
        T = T0 + dTdt * t
        pmin = p_min_n(P, n)
        peq = p_equiv(P, H.force())
        G = G40 * mu_T(P, 40.0) / mu_T(P, T)
        do_event = False
        if scheme == "M0":
            # 持续带压：减压阀出口 p_set+p_cr 经回转接头持续供油，夹紧腔保持 p_set
            H.set_state(P["p_set"], 0.0)
            peq = P["p_set"] / 1.0
            line = P["p_set"] + P["p_cr"]
            V_leak += G * line * dt
            heat += G * line * line * dt
            t_press += dt
        elif scheme == "M1":
            if t >= next_t - 1e-9:
                do_event = True
                next_t = t + 60.0
        elif scheme == "M3":
            if peq < pmin + P["m_trig"] or t >= next_t - 1e-9:
                do_event = True
                next_t = t + 600.0
        elif scheme == "M2":
            pred = last_fill - r_up * (t - last_t)
            if t >= next_t - 1e-9 or pred < pmin + P["m_trig"]:
                do_event = True
        if do_event and t > 0:
            n_ev += 1
            if scheme in ("M1", "M3"):
                # 经旁通座阀快速复压：管路带压 1 s（M1）/0.3 s（M3），夹紧腔充到 p_fill，松开腔经先导泄放
                tp = 1.0 if scheme == "M1" else 0.3
                line = p_fill_nom + P["p_cr"]
                V_leak += G * line * tp
                heat += G * line * line * tp
                t_press += tp
                dV = (p_fill_nom - H.pc) * (P["V_c"] / P["beta_lock"] + P["A2"] ** 2 / H.km)
                V_acc += max(dV, 0) + G * line * tp
                H.set_state(p_fill_nom, 0.0)
                log["events"].append(dict(t=t, type=scheme, pc_before=None))
            else:
                Tm = T + rng.uniform(-P["T_err"], P["T_err"])
                pc_b, pu_b = H.pc, H.pu
                peq_b = p_equiv(P, H.force())
                cfg = dict(p_c0=pc_b, p_u0=max(pu_b, 0.0), T=T, n_rpm=n, leak_mult=scen.get("leak_mult", 1.0),
                           Q_m=q_sched(P, Tm), p_cr_sigma=P["sig_cr"], k_mech=H.km)
                r = measure(P, cfg, sens, rng)
                info, k = r["info"], r["k"]
                V_leak += info["V_leak"]
                heat += info["V_leak"] * (P["p_set"])         # 近似：泄漏×平均压力
                t_press += info["t_pressurized"]
                V_acc += info["V_in"]
                ph = estimate(P, k, Tm, n, cal)
                ev = dict(t=t, type="M2", pc_before=pc_b / 1e6, pu_before=pu_b / 1e6, peq_before=peq_b / 1e6,
                          found=k["found"], reason=k["reason"], est=None if ph is None else ph / 1e6,
                          pc_after=info["p_c_end"] / 1e6, pmin=pmin / 1e6, n=n)
                if ph is not None:
                    est_err.append((ph - pc_b) / 1e3)
                    r_k = (last_fill - ph) / max(t - last_t, 1.0)
                    r_hat = r_k if r_hat is None else P["ewma"] * r_k + (1 - P["ewma"]) * r_hat
                    r_up = max(r_hat, r_k, 50.0) + 2 * 12e3 / max(t - last_t, 1.0)
                    if ph < pmin:
                        alarms.append(dict(t=t, type="夹紧压力低于下限", est=ph / 1e6, pmin=pmin / 1e6))
                    if r_hat > P["r_alarm"]:
                        alarms.append(dict(t=t, type="锁闭压降速率超限（泄漏报警）", r_kPa_s=r_hat / 1e3))
                else:
                    # 未见拐点：压降小于可见下限
                    r_k_up = max(last_fill - (last_fill - dead), 0) / max(t - last_t, 1.0)
                    r_up = min(r_up, r_k_up) if r_hat is None else min(max(r_hat, 50.0), r_k_up)
                    if not info["reached"]:
                        alarms.append(dict(t=t, type="供油压力升不到检测上限（回转接头泄漏过大）"))
                ev["r_up_kPa_s"] = r_up / 1e3
                log["events"].append(ev)
                last_t = t
                last_fill = info["p_c_end"] - 0.0
                H.set_state(info["p_c_end"], max(info["p_u_end"], 0.0))
                interval = (last_fill - (p_min_n(P, n) + P["m_trig"])) / max(r_up, 1.0)
                next_t = t + min(max(interval, P["T_min"]), P["T_max"])
            peq = p_equiv(P, H.force())
        margin = peq - pmin
        min_margin = min(min_margin, margin)
        if margin < 0:
            viol += dt
        if record:
            log["t"].append(t); log["pc"].append(H.pc / 1e6); log["pu"].append(H.pu / 1e6); log["peq"].append(peq / 1e6)
            log["pmin"].append(pmin / 1e6); log["n"].append(n)
        if scheme != "M0":
            H.step(dt, dTdt)
        t += dt
    E_hyd = P["p_acc"] * (V_acc if scheme != "M0" else V_leak) / (P["eta_tot"] * P["eta_motor"])
    return dict(scheme=scheme, 复压或检测次数=n_ev, 回转接头带压时间_s=t_press, 回转接头泄漏_cm3=V_leak / cm3,
                蓄能器耗油_cm3=(V_acc if scheme != "M0" else V_leak) / cm3, 液压能耗_Wh=E_hyd / 3600,
                回转接头节流发热_J=heat, 最小夹紧裕量_MPa=min_margin / 1e6, 低于下限时间_s=viol,
                估计误差_kPa=est_err, 报警=alarms, log=log if record else None)


def _cycle_job(args):
    P, scen_name, scen, scheme, seed, t_end, prog = args
    r = run_cycle(P, scheme, scen, seed=seed, t_end=t_end, prog=prog)
    return scen_name, scheme, r


def st_cycle(P):
    scens = {
        "S1 额定（内泄漏基准，油温 −0.1 K/min）": dict(),
        "S2 冷却（油温 −0.2 K/min）": dict(dTdt=-0.2 / 60),
        "S3 密封磨损（内泄漏×20）": dict(C_int_mult=20.0),
        "S4 密封失效（内泄漏×200）": dict(C_int_mult=200.0),
        "S5 升温（油温 +0.2 K/min）": dict(dTdt=0.2 / 60),
        "S6 回转接头磨损（泄漏×1.6，油温 50 ℃）": dict(leak_mult=1.6, T0=50.0),
    }
    jobs = []
    for i, (sn, sc) in enumerate(scens.items()):
        for scheme in ("M0", "M1", "M2", "M3"):
            jobs.append((P, sn, sc, scheme, SEED + 3000 + i, None, None))
    # 长时保压 1 h，3000 r/min
    prog_long = [[0, 0], [20, 3000], [3580, 3000], [3600, 0]]
    for scheme in ("M1", "M2", "M3"):
        jobs.append((P, "S7 长时保压 1 h（3000 r/min，内泄漏×5）", dict(C_int_mult=5.0), scheme, SEED + 3100, 3600, prog_long))
    with ProcessPoolExecutor(min(NPROC, len(jobs))) as ex:
        res = list(ex.map(_cycle_job, jobs))
    out = {}
    for sn, scheme, r in res:
        out.setdefault(sn, {})[scheme] = r
    # 年能耗（单件循环 656 s，每年 250 班×8 h）
    n_parts = 250 * 8 * 3600 / 656.0
    yr = {}
    for scheme in ("M0", "M1", "M2", "M3"):
        r = out["S1 额定（内泄漏基准，油温 −0.1 K/min）"][scheme]
        yr[scheme] = dict(每件_Wh=r["液压能耗_Wh"], 每年_kWh=r["液压能耗_Wh"] * n_parts / 1000,
                          每年电费_元=r["液压能耗_Wh"] * n_parts / 1000 * P["price"], 每年回转接头泄漏_L=r["回转接头泄漏_cm3"] * n_parts / 1000)
    out["_年"] = dict(件数=n_parts, 方案=yr)
    out["_说明"] = ("M0 持续带压；M1 锁闭+每 60 s 定时复压 1 s（P1 实施例做法，不知夹紧腔压力）；M2 本发明（拐点间接测压+按压降速率与 p_min(n) 自适应复压）；"
                  "M3 旋转侧无线测压+阈值复压（理想测量，成本参照）。能耗按蓄能器供油量×5.5 MPa/(0.8×0.8) 计，未计电机起动与空载。")
    dump("cycle", out)


STAGES = {"validate": st_validate, "curves": st_curves, "supply": st_supply, "sens": st_sens, "mc": st_mc,
          "cycle": st_cycle}

if __name__ == "__main__":
    P = load()
    todo = sys.argv[1:] or list(STAGES)
    for s in todo:
        t0 = time.time()
        print("==", s, flush=True)
        STAGES[s](P)
        print("== 完成", s, round(time.time() - t0, 1), "s", flush=True)
