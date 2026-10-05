# -*- coding: utf-8 -*-
"""仿真主程序（分阶段落盘）。用法：python sim_all.py [stage ...]
stage：validate scen stiff energy chuck sens mc （缺省全部）。结果写 数据/<stage>.json。
方案对应：方案1=M0 原定量泵溢流保压；方案2=M1s 单腔锁闭+蓄能器（压力继电器下限补油）；
方案3=M1b 恒压减压供油（蓄能器经三通减压阀持续接无杆腔）；方案4=M2 本发明（双腔预压锁闭+事件触发双向回复，方案甲）。
补充：M2b 本发明方案乙、M2S 消融（单腔锁闭+带控）、M2h 锁闭腔含软管。"""
import json, math, os, sys, time, platform
import numpy as np, scipy
import params as PR
import hydro as H
import tail_qs as Q
import tail_dyn as D
import stiffness as S
import energy as E
from params import MPa, cm3

SEED = 20261001
MAIN = ["M0", "M1s", "M1b", "M2"]
LABEL = {"M0": "方案1 原定量泵溢流", "M1s": "方案2 单腔锁闭+蓄能器", "M1b": "方案3 恒压减压供油",
         "M2": "方案4 本发明(甲)", "M2b": "本发明(乙)", "M2S": "消融:单腔锁闭+带控", "M2h": "本发明含软管"}


def qs_scheme(s):          # 推力行为：M0 与 M1b 同为三通减压阀持续供油
    return "M1b" if s == "M0" else s


def dump(name, obj):
    obj["_meta"] = {"时间": time.strftime("%Y-%m-%d %H:%M:%S"), "python": platform.python_version(),
                    "numpy": np.__version__, "scipy": scipy.__version__, "seed": SEED}
    p = os.path.join(PR.DATA, name + ".json")
    json.dump(obj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print("written", p)


# ---------------------------------------------------------------- 工况
def cases(P):
    g1 = Q.ramp_growth(57.5e-6, 300.0)
    g2 = Q.ramp_growth(138e-6, 600.0)
    z = lambda t: 0.0
    return {
        "C1 工件伸长57.5um(τ5min)": dict(d=g1, T=z, lm=0.0, t=600),
        "C2 细长轴伸长138um(τ10min)": dict(d=g2, T=z, lm=0.0, t=600),
        "C3 油温升+0.2K/min": dict(d=z, T=Q.linear_temp(0.2 / 60), lm=0.0, t=600),
        "C4 油温降-0.2K/min": dict(d=z, T=Q.linear_temp(-0.2 / 60), lm=0.0, t=600),
        "C5 泄漏(内泄漏×4,恒温)": dict(d=z, T=z, lm=4.0, t=600),
        "C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)": dict(d=g1, T=Q.linear_temp(0.1 / 60), lm=1.0, t=600),
        "C7 长时保压1h(油温日变化-5K/h)": dict(d=z, T=Q.linear_temp(-5 / 3600), lm=1.0, t=3600),
    }


def run_case(P, s, c, dt=1.0, sensor_err=True, seed=SEED, **kw):
    tl = Q.Tail(P, qs_scheme(s), seed=seed, sensor_err=sensor_err, **kw)
    r, o = tl.run(c["t"], dt, c["d"], c["T"], leak_mult=c["lm"])
    r["取油cm3"] = tl.in_acc / cm3
    return r, o, tl


# ---------------------------------------------------------------- 1 求解器校核
def st_validate(P):
    out = {}
    P0 = dict(P); P0["air_frac"] = 0.0
    x = P["x_nom"]; Vd = P["Vd_block"]; b = P["beta_lock"]
    rows = []
    for dual, s in ((True, "M2"), (False, "M2S")):
        Ka = H.K_series(x, P0, Vd, b, b, dual) / 1e6
        Ta = H.thermal_N_per_K(x, P0, Vd, b, dual)
        tl = Q.Tail(P0, s, sensor_err=False, Fs=0.0)
        F0 = tl.Fw(); tl.delta = 1e-6; tl.equilibrate(); Kn = (tl.Fw() - F0)
        tl = Q.Tail(P0, s, sensor_err=False, Fs=0.0)
        tl.T = 0.01; tl.equilibrate(); Tn = (tl.Fw() - F0) / 0.01
        rows.append({"方案": s, "刚度解析N_um": Ka, "刚度数值N_um": Kn, "刚度相对误差": Kn / Ka - 1,
                     "热漂移解析N_K": Ta, "热漂移数值N_K": Tn, "热漂移相对误差": Tn / Ta - 1})
    out["准静态模型_对解析式"] = rows
    out["设计基准推导值"] = {"K单腔": 33.3, "K双腔": 45.5, "热漂移单腔": 1746, "热漂移双腔": 440}
    # 动态模型：Fs=0、载荷阶跃，与静变形和固有频率解析值对比
    k1, k2 = H.k_oil(x, P0, Vd, b, b, True)
    dyn = []
    for rtol, ms in ((1e-4, 1e-3), (1e-6, 1e-3), (1e-8, 2e-4), (1e-9, 5e-5)):
        T = D.TailDyn(P0, "M2", Fs=0.0); T.R1_on = T.R2_on = False
        T.dF = lambda t: 1000.0 if t > 0.005 else 0.0
        t0 = time.time()
        r = T.run(0.25, rtol=rtol, max_step=ms, t_eval=np.linspace(0, 0.25, 25001))
        dx = r["x"] - r["x"][0]
        ii = r["t"] > 0.005
        tt, xx = r["t"][ii], dx[ii]
        xm = xx - xx[-2000:].mean()
        zc = tt[1:][(xm[:-1] < 0) & (xm[1:] >= 0)]
        f = 1 / np.mean(np.diff(zc[:6])) if len(zc) > 3 else float("nan")
        dyn.append({"rtol": rtol, "max_step_s": ms, "静位移um": float(-xx[-2000:].mean() * 1e6),
                    "峰值um": float(-xx.min() * 1e6), "振荡频率Hz": float(f), "nfev": int(r["nfev"]),
                    "耗时s": time.time() - t0})
    m, c = P["m_pist"], P["c_visc"]; ko = k1 + k2
    wn = math.sqrt(ko / m); z = c / (2 * math.sqrt(ko * m))
    out["动态模型"] = {"解析静位移um": 1000 / ko * 1e6, "解析阻尼固有频率Hz": wn * math.sqrt(1 - z * z) / 2 / math.pi,
                     "解析超调峰值um": 1000 / ko * 1e6 * (1 + math.exp(-z * math.pi / math.sqrt(1 - z * z))),
                     "阻尼比": z, "收敛": dyn}
    # 准静态步长收敛（综合工况，传感误差关闭）
    cc = cases(P)["C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"]
    conv = []
    for dt in (4.0, 2.0, 1.0, 0.5, 0.25):
        for s in ("M1s", "M2"):
            r, o, _ = run_case(P, s, cc, dt=dt, sensor_err=False)
            F = np.array(o["F_N"])
            conv.append({"dt_s": dt, "方案": s, "推力最大N": r["推力最大N"], "推力最小N": r["推力最小N"],
                         "终值N": float(F[-1]), "动作次数": r["动作次数"]})
    out["准静态步长收敛"] = conv
    # 准静态 vs 动态（复位过程终值）
    T = D.TailDyn(P, "M2"); y = T.y0(); y[2] += 0.4e6
    T.cmd["V1"] = [(0.05, 0.35)]; T.cmd["V4"] = [(0.05, 0.35)]; T.k_w = P["k_m"]
    r = T.run(0.8, y0=y)
    tl = Q.Tail(P, "M2", sensor_err=False); tl.T = 0.0
    tl.m1 = H.mass_of(H.chamber_volumes(tl.x, P, tl.Vd)[0], tl.p1 + 0.4e6, 0, P, tl.beta); tl.equilibrate()
    Fq0 = tl.Fw(); tl.reset_3way(1, tl.p1_set); tl.reset_3way(2, tl.p2_set)
    out["复位过程_动态对准静态"] = {"动态初推力N": float(r["Fh"][0]), "动态终推力N": float(r["Fh"][-1]),
                              "准静态初推力N": Fq0, "准静态终推力N": tl.Fw(),
                              "动态p1终MPa": float(r["p1"][-1] / MPa), "动态p2终MPa": float(r["p2"][-1] / MPa),
                              "准静态p1终MPa": tl.p1 / MPa, "准静态p2终MPa": tl.p2 / MPa,
                              "说明": "两模型初始状态不同（动态模型初始无摩擦平衡，准静态模型含静摩擦平衡），比较终了压力",
                              "开阀后进入推力带(±5%)用时s": float(r["t"][np.where(np.abs(r["Fh"] - P["F0"]) > 0.05 * P["F0"])[0][-1]] - 0.05),
                              "t": r["t"][::10].tolist(), "Fh": r["Fh"][::10].tolist(), "Fw": r["Fw"][::10].tolist()}
    m0 = E.p_hold_M0(P)
    out["M0能耗_对AMESim"] = {"本模型泵轴功率kW": m0["泵轴功率W"] / 1e3, "AMESim泵输入kW": 1.24,
                           "本模型溢流损失kW": m0["溢流损失W"] / 1e3, "AMESim溢流损失kW": 1.22}
    dump("validate", out)


# ---------------------------------------------------------------- 2 工况
def dl_err(o):
    """工件热伸长量估算误差（v1.1 新增，对应说明书式（4）/权利要求 8、21 的“推力变化扣除油温项再除以刚度”法 dL1；
    dL2 为两腔压力—油温体积法，dL3 为位移传感器法，仅作对照）。真值为 delta_um。"""
    d = np.array(o["delta_um"])
    r = {"伸长真值终值um": float(d[-1]), "伸长真值最大um": float(d.max())}
    for k, nm in (("dL1_um", "推力油温法"), ("dL2_um", "体积法"), ("dL3_um", "位移传感器法")):
        e = np.array(o[k], dtype=float) - d
        if np.all(np.isnan(e)):
            continue
        r[nm] = {"最大绝对误差um": float(np.nanmax(np.abs(e))), "终值误差um": float(e[-1]),
                 "终值估算um": float(np.array(o[k], dtype=float)[-1])}
    return r


def st_scen(P):
    out = {"工况": {}, "时程": {}}
    for cn, c in cases(P).items():
        out["工况"][cn] = {}
        for s in ["M0", "M1s", "M1b", "M2", "M2b", "M2S", "M2h"]:
            if s == "M0":
                continue
            r, o, tl = run_case(P, s, c)
            r["事件"] = [(e[0], e[1]) for e in tl.events][:400]
            out["工况"][cn][s] = r
            if cn.startswith(("C1", "C3", "C4", "C6", "C7")) and s in ("M1s", "M1b", "M2", "M2S"):
                k = max(1, len(o["t"]) // 1200)
                out["时程"].setdefault(cn, {})[s] = {kk: o[kk][::k] for kk in
                                                    ("t", "F_N", "Fest_N", "p1_MPa", "p2_MPa", "x_mm", "delta_um", "T_K", "dL1_um", "dL2_um", "dL3_um")}
            if s in ("M2", "M2S"):
                out.setdefault("ΔL估算", {}).setdefault(cn, {})[s] = dl_err(o)
        # 无测量误差（传感器偏差、噪声、标定误差均为 0）时的 ΔL 估算误差，用于分离模型误差与测量误差
        r0, o0, _ = run_case(P, "M2", c, sensor_err=False)
        out["ΔL估算"][cn]["M2_无测量误差"] = dict(dl_err(o0), 动作次数=r0["动作次数"], 最大正偏差=r0["最大正偏差%"],
                                              最大负偏差=r0["最大负偏差%"])
        out["工况"][cn]["M0"] = dict(out["工况"][cn]["M1b"], 方案="M0", 名称="M0 原系统（推力行为同 M1b）")
    # v1.1：内泄漏取基准值 0.1 倍时的综合工况 ΔL 估算误差（说明内泄漏对推力油温法的影响）
    c6 = cases(P)["C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"]
    r, o, _ = run_case(P, "M2", dict(c6, lm=0.1))
    out["ΔL估算"]["C6 综合_内泄漏×0.1"] = {"M2": dl_err(o), "动作次数": r["动作次数"]}
    # 切削力阶跃（动态模型）
    out["切削力阶跃"] = {}
    for s in ("M1s", "M1b", "M2", "M2S"):
        for dF in (500.0, 1000.0, 2000.0):
            r = S.step_response(P, s, dF=dF, t_end=0.3)
            u = r["顶尖位移um"]
            out["切削力阶跃"].setdefault(s, {})[str(int(dF))] = {"终值um": float(u[-1]), "峰值um": float(u.min()),
                                                                "t": r["t"][::10].tolist(), "u": u[::10].tolist()}
    # 安全上限：突发 1.3F0 (伸长阶跃)
    dump("scen", out)


# ---------------------------------------------------------------- 3 刚度
def st_stiff(P):
    xs = np.linspace(P["x_range"][0], P["x_range"][1], 23)
    out = {"伸出量mm": (xs * 1e3).tolist(), "静刚度N_um": {}, "油柱刚度N_um": {}}
    L = ("M2", "M2h", "M2S", "M1s", "M1", "M1b")
    for s in L:
        Ks, Ko = zip(*[S.K_center(P, s, x) for x in xs])
        out["静刚度N_um"][s] = [k / 1e6 for k in Ks]; out["油柱刚度N_um"][s] = [k / 1e6 for k in Ko]
    nom = {s: S.K_center(P, s, P["x_nom"])[0] / 1e6 for s in L}
    out["额定静刚度N_um"] = nom
    out["M1b不灵敏区N"] = P["red_db"] * P["A1"]
    f = np.logspace(0, np.log10(1500), 300)
    out["频率Hz"] = f.tolist()
    out["动柔度um_N"] = {s: (S.compliance_frf(P, s, f) * 1e6).tolist() for s in ("M2", "M2S", "M1s", "M1b")}
    out["动刚度N_um"] = {s: {str(ff): float(1 / S.compliance_frf(P, s, [ff])[0] / 1e6) for ff in (0.1, 1.0, 10.0, 100.0)}
                       for s in ("M2", "M2S", "M1s", "M1b")}
    # 热漂移敏感系数（解析，含空气修正前）
    out["热漂移N_K"] = {"M2": H.thermal_N_per_K(P["x_nom"], P, P["Vd_block"], P["beta_lock"], True),
                      "M2S": H.thermal_N_per_K(P["x_nom"], P, P["Vd_block"], P["beta_lock"], False),
                      "M1s": H.thermal_N_per_K(P["x_nom"], P, P["Vd_block"] + P["Vd_hose"], P["beta_hose"], False)}
    out["热漂移_伸出量"] = {s: [H.thermal_N_per_K(x, P, P["Vd_block"], P["beta_lock"], d) for x in xs]
                         for s, d in (("M2", True), ("M2S", False))}
    # v1.1（独立复核问题 2）：计入未溶解空气 0.5% 后的热漂移系数，由准静态模型数值求得（F_s=0，无测量误差）。
    # 上面的“热漂移N_K”为解析值（不计空气），二者口径不同。
    drift = {}
    for s in ("M2", "M2S", "M1s"):
        tl = Q.Tail(P, s, sensor_err=False, Fs=0.0)
        F0 = tl.Fw(); tl.T = 0.01; tl.equilibrate()
        drift[s] = (tl.Fw() - F0) / 0.01
    out["热漂移_含空气数值N_K"] = drift
    # p_pre 扫描：刚度与热漂移
    pp = np.linspace(0.0, 3.0, 13)
    out["p_pre扫描"] = []
    for p in pp:
        P2 = dict(P); P2["p_pre"] = p * MPa
        # v1.1（独立复核发现）：v1 未随 p_pre 更新 p1_set，无杆腔压力固定为 2.962 MPa；现按式（2）同步更新
        P2["p1_set"] = (P["F0"] + p * MPa * P["A2"]) / P["A1"]
        k1, k2, _ = S.k_oil_static(P2, "M2", P["x_nom"])
        Kc = S.K_center(P2, "M2", P["x_nom"])[0] / 1e6
        out["p_pre扫描"].append({"p_pre": p, "K_N_um": Kc, "p1_set": (P["F0"] + p * MPa * P["A2"]) / P["A1"] / MPa})
    dump("stiff", out)


# ---------------------------------------------------------------- 4 能耗
def st_energy(P):
    scen = json.load(open(os.path.join(PR.DATA, "scen.json"), encoding="utf-8"))
    out = {"保压630s": {}, "单件循环": {}, "年": {}}
    cn = "C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"
    th = P["cycle"]["保压加工"] + P["cycle"]["装卸"]
    for s in MAIN + ["M2b"]:
        Vc = 0.0 if s == "M0" else scen["工况"][cn][s]["取油cm3"] * cm3 * th / 600
        h = E.hold_energy(P, s, th, V_ctrl=Vc)
        c = E.cycle_energy(P, s, V_ctrl=Vc)
        out["保压630s"][s] = h; out["单件循环"][s] = c; out["年"][s] = E.annual(P, c)
    b = out["单件循环"]["M0"]["单件电能kWh"]
    out["相对M0节能%"] = {s: 100 * (1 - out["单件循环"][s]["单件电能kWh"] / b) for s in out["单件循环"]}
    # 能耗分解敏感性：回转接头泄漏、滑阀泄漏
    sw = []
    for rot in (0.1, 0.35, 0.7, 1.4):
        for sp in (1.0, 5.0, 10.0):
            P2 = dict(P); P2["C_rot"] = rot * 1e-3 / 60 / (3 * MPa); P2["C_spool"] = sp * cm3 / 60 / MPa
            sw.append({"回转接头L_min@3MPa": rot, "滑阀cm3_min_MPa": sp,
                       **{s: E.hold_energy(P2, s, th)["平均轴功率W"] for s in ("M1s", "M1b", "M2")}})
    out["泄漏敏感性_平均轴功率W"] = sw
    dump("energy", out)


# ---------------------------------------------------------------- 5 卡盘卸压与复压
def chuck_sim(P, t_end=630.0, dt=0.5, t_rep=60.0, dTdt=-0.2 / 60, scheme="M2"):
    """卡盘夹紧腔（有杆腔）锁闭：内置液控单向阀，换向阀中位卸掉回转接头压力。
    夹紧腔压力：dp = β/V (−C_chk p + αV dT/dt)；每 t_rep 复压到 p_chuck（1 s）。
    现有技术：回转接头持续带压，压力恒定，泄漏 C_rot·p 由蓄能器承担。"""
    b, V = P["beta_lock"], P["V_chuck_lock"]
    n = int(t_end / dt); t = np.arange(n + 1) * dt; p = np.zeros(n + 1); p[0] = P["p_chuck"]
    Vrep = 0.0; nrep = 0
    for k in range(1, n + 1):
        if scheme == "M2":
            p[k] = p[k - 1] + b / V * (-P["C_chk"] * p[k - 1] + P["alpha_v"] * V * dTdt) * dt
            if t[k] % t_rep < dt / 2:
                Vrep += (P["p_chuck"] - p[k]) * V / b + P["C_rot"] * P["p_chuck"] * 1.0
                p[k] = P["p_chuck"]; nrep += 1
        else:
            p[k] = P["p_chuck"]
    leak = Vrep if scheme == "M2" else P["C_rot"] * P["p_chuck"] * t_end
    return t, p, {"复压次数": nrep, "耗油cm3": leak / cm3, "最低压力MPa": float(p.min() / MPa),
                  "最高压力MPa": float(p.max() / MPa), "最大夹紧力降%": float(100 * (1 - p.min() / P["p_chuck"]))}


def st_chuck(P):
    out = {"工况": {}}
    for nm, r in (("油温降0.2K/min", -0.2 / 60), ("油温降0.05K/min", -0.05 / 60), ("恒温", 0.0), ("油温升0.2K/min", 0.2 / 60)):
        for tr in (30.0, 60.0, 120.0):
            t, p, s = chuck_sim(P, dTdt=r, t_rep=tr)
            out["工况"][f"{nm}_复压{int(tr)}s"] = s
            if tr == 60.0 and nm == "油温降0.2K/min":
                out["时程"] = {"t": t[::4].tolist(), "p_MPa": (p[::4] / MPa).tolist()}
    t, p, s = chuck_sim(P, scheme="M1")
    out["现有技术_回转接头持续带压"] = s
    # 允许复压间隔：压力降不超过 Δp_allow
    out["压力—油温系数MPa_K"] = P["beta_lock"] * P["alpha_v"] / MPa
    for allow in (0.05, 0.1):
        out[f"允许降{int(allow*100)}%时最长复压间隔s_0.2K/min"] = allow * P["p_chuck"] / (P["beta_lock"] * P["alpha_v"] * 0.2 / 60)
    dump("chuck", out)


# ---------------------------------------------------------------- 6 敏感性（单因素）
SENS = [("beta_lock", "体积模量MPa", [800e6, 1200e6, 1600e6], 1 / MPa),
        ("p_pre", "预压p_pre MPa", [0.5e6, 1.0e6, 1.5e6, 2.0e6, 3.0e6], 1 / MPa),
        ("F_s", "静摩擦N", [50.0, 150.0, 300.0], 1.0),
        ("k_m", "机械刚度N_um", [50e6, 100e6, 200e6], 1e-6),
        ("band", "推力带宽±", [0.02, 0.05, 0.10], 1.0),
        ("x_nom", "伸出量mm", [0.02, 0.07, 0.13], 1e3),
        ("F0", "目标推力N", [2000.0, 6000.0, 12000.0], 1.0),
        ("C_int_mult", "内泄漏倍数", [0.1, 1.0, 4.0], 1.0),
        ("air_frac", "未溶解空气", [0.0, 0.005, 0.02], 1.0)]


def sens_metric(P, s):
    cc = cases(P)["C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"]
    cc = dict(cc, lm=P.get("C_int_mult", 1.0))
    Fs = P["F_s"]
    r, o, tl = run_case(P, s, cc, sensor_err=False, Fs=Fs)
    F0 = P["F0"]
    return {"最大偏差%": max(r["最大正偏差%"], -r["最大负偏差%"]), "动作次数": r["动作次数"],
            "静刚度N_um": S.K_center(P, s, P["x_nom"])[0] / 1e6}


def st_sens(P):
    out = []
    for key, nm, vals, sc in SENS:
        for v in vals:
            P2 = dict(P); P2[key] = v
            if key == "beta_lock":       # v1.1：与蒙特卡洛一致，含软管方案的体积模量按同一比例变化
                P2["beta_hose"] = v * 800 / 1200
            if key in ("p_pre", "F0"):
                P2["p1_set"] = (P2["F0"] + P2["p_pre"] * P2["A2"]) / P2["A1"]
            row = {"参数": nm, "值": v * sc}
            for s in ("M1s", "M1b", "M2", "M2S"):
                try:
                    row[s] = sens_metric(P2, s)
                except Exception as e:
                    row[s] = {"错误": str(e)}
            out.append(row)
            print(nm, v * sc, {s: round(row[s].get("最大偏差%", -1), 2) for s in ("M1s", "M2")})
    # v1.1（审查意见 G1）：三通减压阀回差（减压—溢流不灵敏区 red_db）与推力带宽的匹配；rev_center 为设定值下移 red_db/2
    db_rows = []
    for band in (0.02, 0.05):
        for db in (0.05, 0.10, 0.20):
            for rc in (False, True):
                P2 = dict(P); P2["band"] = band; P2["red_db"] = db * MPa; P2["rev_center"] = rc
                cc = cases(P2)["C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"]
                r, o, tl = run_case(P2, "M2", cc, sensor_err=False)
                db_rows.append({"推力带δ": band, "回差MPa": db, "设定下移半个回差": rc,
                                "回差折合推力/带半宽": db * MPa * P["A1"] / (band * P["F0"]),
                                "最大正偏差%": r["最大正偏差%"], "最大负偏差%": r["最大负偏差%"], "动作次数": r["动作次数"]})
    dump("sens", {"单因素": out, "减压阀回差": db_rows})


# ---------------------------------------------------------------- 7 蒙特卡洛
def st_mc(P, N=None):
    N = int(os.environ.get("MC_N", "1000")) if N is None else N
    rng = np.random.default_rng(SEED)
    rows = []
    t0 = time.time()
    for i in range(N):
        P2 = dict(P)
        P2["beta_lock"] = rng.uniform(800e6, 1600e6)
        P2["beta_hose"] = P2["beta_lock"] * 800 / 1200
        P2["F_s"] = rng.uniform(50, 300)
        P2["k_m"] = rng.uniform(50e6, 200e6)
        P2["air_frac"] = rng.uniform(0.0, 0.01)
        lm = 10 ** rng.uniform(-1, math.log10(4))
        x = rng.uniform(0.02, 0.13)
        dL = rng.uniform(20e-6, 140e-6); tau = rng.uniform(180, 900)
        dTr = rng.uniform(-0.2, 0.2) / 60
        P2["x_nom"] = x
        c = dict(d=Q.ramp_growth(dL, tau), T=Q.linear_temp(dTr), lm=lm, t=600)
        row = {"beta": P2["beta_lock"] / MPa, "Fs": P2["F_s"], "km": P2["k_m"] / 1e6, "leak": lm, "x_mm": x * 1e3,
               "dL_um": dL * 1e6, "tau_s": tau, "dTdt_K_min": dTr * 60}
        for s in ("M1s", "M1b", "M2", "M2b"):
            try:
                r, o, tl = run_case(P2, s, c, dt=2.0, sensor_err=True, seed=SEED + i)
                row[s] = {"正偏差%": r["最大正偏差%"], "负偏差%": r["最大负偏差%"], "动作": r["动作次数"], "取油cm3": r["取油cm3"]}
            except Exception as e:
                row[s] = {"错误": str(e)}
        rows.append(row)
        if i % 100 == 0:
            print(i, time.time() - t0)
    summ = {}
    for s in ("M1s", "M1b", "M2", "M2b"):
        ok = [r[s] for r in rows if "错误" not in r[s]]
        dev = np.array([max(a["正偏差%"], -a["负偏差%"]) for a in ok]); up = np.array([a["正偏差%"] for a in ok])
        act = np.array([a["动作"] for a in ok])
        summ[s] = {"样本": len(ok), "失败": len(rows) - len(ok), "最大偏差均值%": float(dev.mean()), "P95%": float(np.percentile(dev, 95)),
                   "最大%": float(dev.max()), "正偏差P95%": float(np.percentile(up, 95)),
                   "偏差>10%比例": float(np.mean(dev > 10)), "超安全上限25%比例": float(np.mean(up > 25)),
                   "动作次数均值": float(act.mean()), "动作次数P95": float(np.percentile(act, 95))}
        # 收敛：前 n 个样本的 P95
        summ[s]["P95收敛"] = {str(n): float(np.percentile(dev[:n], 95)) for n in (100, 250, 500, len(dev)) if n <= len(dev)}
        bs = [np.percentile(rng.choice(dev, len(dev)), 95) for _ in range(500)]
        summ[s]["P95_95%CI"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    dump("mc", {"N": N, "汇总": summ, "样本": rows})


STAGES = {"validate": st_validate, "scen": st_scen, "stiff": st_stiff, "energy": st_energy,
          "chuck": st_chuck, "sens": st_sens, "mc": st_mc}

if __name__ == "__main__":
    P = PR.load()
    for st in (sys.argv[1:] or list(STAGES)):
        t0 = time.time(); STAGES[st](P); print(st, "done", round(time.time() - t0, 1), "s")
