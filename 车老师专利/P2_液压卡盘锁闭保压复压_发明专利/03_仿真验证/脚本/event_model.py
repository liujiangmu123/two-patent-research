# -*- coding: utf-8 -*-
"""一次“检测复压”事件的毫秒级动态模型（P2 核心）。

两种布置（cfg["layout"]）：
- "joint"（本发明优选）：调速阀、比例三通减压阀和压力传感器 S1 集成在回转接头静止壳体进油口处的检测阀块上，
  软管在调速阀上游（检测期间充满蓄能器压力，不参与检测容腔）。检测容腔 = 阀块内腔 + 回转接头与旋转侧油道。
- "plate"（对比/改装）：调速阀与减压阀装在阀板上，经换向阀、软管（N 段集总：容腔+惯性+层流阻力）到 S1。

公共部分：节点 s（回转接头进油口，S1，配合间隙泄漏 G·p_s）→ 旋转侧油道（层流阻力 R_path，离心升压）→ 节点 r
（夹紧侧液控单向阀进口，并推动松开侧单向阀的先导活塞）→ 夹紧侧单向阀（质量—弹簧—阻尼锥阀，开启压差 p_cr）→ 夹紧腔 c；
松开腔 u 在先导打开后泄放。活塞—拉杆—卡爪机构：质量 m、等效刚度 k_mech、阻尼比 ζ；rigid=True 为刚性极限。
旋转：c、u 压力取环形面积平均值（决定活塞力）；单向阀出口处压力 = p_c + ρω²(r_cv²−re²)/2；
油道从油槽半径 r_g 到 r_cv 的离心升压 ρω²(r_cv²−r_g²)/2。求解：SciPy BDF。
"""
import math

import numpy as np
from scipy.integrate import solve_ivp

from params import MPa, Lmin, cm3, beta_eff, G_rot, mu_T


def clip01(x):
    return min(1.0, max(0.0, x))


class Event:
    def __init__(self, P, cfg=None):
        self.P = P
        c = dict(layout="joint", N=6, n_rpm=0.0, T=40.0, leak_mult=1.0, k_mech=P["k_mech"], rigid=False,
                 p_c0=1.85 * MPa, p_u0=0.02 * MPa, p_red=None, Q_m=P["Q_m"], p_cr=P["p_cr"],
                 V_hose=P["V_hose"], V_metal=P["V_metal"], V_joint=13 * cm3, p_po=P["p_po"], C_int=P["C_int"],
                 surge=0.3, t_max=0.8, t_hold=P["t_hold"], t_vent=0.06, beta_lock=P["beta_lock"], air=P["air_frac"],
                 unsteady_fric=1.5, R_path_mult=1.0, fcv_mode="fcv", ramp_rate=None, ramp_p0=0.0, A_orif=None,
                 k_spr=P["k_spr"], c_pop=P["c_pop"], Q_m_err=0.0, V_pp=P["V_pp"], tau_pp=2e-3)
        # V_pp：松开侧单向阀先导活塞排量；tau_pp：先导活塞跟随时间常数（assumption 2 ms，含先导油道节流）。
        # 2026-10-01 续做：validate 中“拐点前斜率 −50%”即由先导活塞在快速升压段仍在吸油（一阶滞后尾段）
        # 以及原拟合窗口伸入先导活塞动作平台段造成，见 仿真验证报告 第 4.1 节。
        if cfg:
            c.update(cfg)
        if c["p_red"] is None:
            c["p_red"] = P["p_set"] + P["p_cr"] + P["d_c_ceiling"]
        self.c = c
        self.joint = c["layout"] == "joint"
        N = 0 if self.joint else c["N"]
        self.N = N
        # 状态索引
        I = {}
        k = 0
        if not self.joint:
            I["src"] = 0
            I["ph"] = slice(1, 1 + N)
            I["qh"] = slice(1 + N, 1 + 2 * N)
            k = 1 + 2 * N
        for name in ("ps", "pr", "xv", "vv", "pc", "pu", "xp", "vp", "ypp", "Vin", "Vleak", "Vcv", "Vrel"):
            I[name] = k
            k += 1
        I["n"] = k
        self.I = I
        rho = P["rho"]
        self.w = 2 * math.pi * c["n_rpm"] / 60
        self.dp_w_path = rho * self.w ** 2 * (P["r_cv"] ** 2 - P["r_g"] ** 2) / 2
        self.dp_w_out = rho * self.w ** 2 * (P["r_cv"] ** 2 - P["re2"]) / 2
        mu = mu_T(P, c["T"])
        self.R_path = c["R_path_mult"] * 128 * mu * P["L_path"] / (math.pi * P["d_path"] ** 4)
        self.G = G_rot(P, c["T"], c["leak_mult"])
        if self.joint:
            Vj = c["V_joint"]
            self.V_s = 3 * cm3 * Vj / (13 * cm3)
            self.V_r = Vj - self.V_s
        else:
            Ah = math.pi / 4 * P["d_hose"] ** 2
            Lseg = P["L_hose"] / N
            self.Vh = c["V_hose"] / N
            self.Ih = rho * Lseg / Ah
            self.Rh = c["unsteady_fric"] * 128 * mu * Lseg / (math.pi * P["d_hose"] ** 4)
            Vm = c["V_metal"]
            self.V_src = P["V_src"] * Vm / P["V_metal"]
            self.V_s = 2 * cm3 * Vm / P["V_metal"]
            self.V_r = Vm - self.V_src - self.V_s
        self.rigid = c["rigid"] or c["k_mech"] is None
        km = 0.0 if self.rigid else c["k_mech"]
        self.km = km
        self.cm = 0.0 if self.rigid else 2 * P["zeta_mech"] * math.sqrt(km * P["m_pist"])
        self.F0 = c["p_c0"] * P["A2"] - c["p_u0"] * P["A1"]
        self.x0v = c["p_cr"] * P["A_seat"] / c["k_spr"]
        self.cv_k = P["Cd"] * math.pi * P["d_seat"] * math.sin(P["half_cone"]) * math.sqrt(2 / rho)
        self.Qm = c["Q_m"] * (1 + c["Q_m_err"])
        self.on, self.t_switch = True, 0.0

    # ---------------------------------------------------------------- 阀与供油
    def dv_open(self, t):
        P = self.P
        a = clip01((t - self.t_switch - P["t_dv_delay"]) / P["t_dv_open"])
        return a if self.on else 1 - a

    def source(self, t, p_out):
        """检测供油：返回 (流入流量, 二次侧溢流流量)。p_out 为减压阀出口压力。"""
        P, c = self.P, self.c
        ts = t - self.t_switch - P["t_dv_delay"] - (P["t_dv_open"] if self.joint else 0.0)
        if c["fcv_mode"] == "fcv":
            if self.joint and not self.on:
                return 0.0, 0.0
            if self.joint and ts < 0:
                return 0.0, 0.0
            surge = c["surge"] * math.exp(-max(ts, 0) / P["tau_fcv"]) if ts > 0 else 0.0
            q = self.Qm * (1 + surge) * clip01((c["p_red"] - p_out) / P["pb_red"])
        elif c["fcv_mode"] == "orifice":
            if self.joint and (not self.on or ts < 0):
                return 0.0, 0.0
            dp = max(P["p_acc"] - p_out, 0.0)
            q = c["A_orif"] * P["Cd"] * math.sqrt(2 * dp / P["rho"]) * clip01((c["p_red"] - p_out) / P["pb_red"])
        elif c["fcv_mode"] in ("ramp", "ramp_orif"):
            pset = c["ramp_p0"] + c["ramp_rate"] * max(ts, 0.0) if self.on else c["p_red"]
            pset = min(pset, c["p_red"])
            Kq = 30 * Lmin / (0.2 * MPa)          # assumption：比例减压阀压力—流量增益
            e = pset - p_out
            if self.joint and (not self.on or ts < 0):
                return 0.0, 0.0
            return min(max(Kq * e, 0.0), 20 * Lmin), max(-Kq * e, 0.0)
        else:
            raise ValueError(c["fcv_mode"])
        rel = 2e-11 * max(p_out - c["p_red"] - P["db_rel"], 0.0)
        return q, rel

    # ---------------------------------------------------------------- 右端
    def rhs(self, t, y):
        P, c, I = self.P, self.c, self.I
        rho, air = P["rho"], c["air"]
        d = np.zeros_like(y)
        ps, pr, xv, vv, pc, pu, xp, vp, ypp = (y[I[k]] for k in ("ps", "pr", "xv", "vv", "pc", "pu", "xp", "vp", "ypp"))
        if self.joint:
            a = self.dv_open(t)
            if c["fcv_mode"] == "ramp_orif":           # 理想斜坡压力源经固定节流孔接入
                ts = t - self.t_switch - P["t_dv_delay"] - P["t_dv_open"]
                pset = min(c["ramp_p0"] + c["ramp_rate"] * max(ts, 0.0), c["p_red"]) if (self.on and ts > 0) else 0.0
                dpo = pset - ps
                qin = c["A_orif"] * P["Cd"] * math.sqrt(2 / rho) * dpo / math.sqrt(abs(dpo) + 2e4) if (self.on and ts > 0) else 0.0
                qrel = 0.0
            else:
                qin, qrel = self.source(t, ps)
            # 断电后：经调速阀反向单向阀、软管、换向阀 A→T 泄放
            Qvent = P["Cd"] * P["A_bt"] * (1 - a) * math.sqrt(2 / rho) * ps / math.sqrt(abs(ps) + 2e4) if not self.on else 0.0
            Q_into_s = qin - qrel - Qvent
            d[I["Vin"]], d[I["Vrel"]] = qin, qrel
        else:
            N = self.N
            p_src = y[I["src"]]
            ph = y[I["ph"]]
            qh = y[I["qh"]]
            a = self.dv_open(t)
            dp = p_src - ph[0]
            A_pa = c["A_orif"] if c["fcv_mode"] == "ramp_orif" else P["A_dv"]
            Qpa = P["Cd"] * A_pa * a * math.sqrt(2 / rho) * dp / math.sqrt(abs(dp) + 2e4)
            Qat = P["Cd"] * P["A_bt"] * (1 - a) * math.sqrt(2 / rho) * ph[0] / math.sqrt(abs(ph[0]) + 2e4)
            qin, qrel = self.source(t, p_src)
            d[I["src"]] = (qin - qrel - Qpa) * beta_eff(p_src, P["beta_m"], air) / self.V_src
            d[I["Vin"]], d[I["Vrel"]] = qin, qrel
            pn = np.append(ph[1:], ps)
            for i in range(N):
                qi_in = Qpa - Qat if i == 0 else qh[i - 1]
                d[I["ph"].start + i] = (qi_in - qh[i]) * beta_eff(ph[i], P["beta_h"], air) / self.Vh
                d[I["qh"].start + i] = (ph[i] - pn[i] - self.Rh * qh[i]) / self.Ih
            Q_into_s = qh[N - 1]
        Qleak = self.G * max(ps, 0.0)
        Qpath = (ps + self.dp_w_path - pr) / self.R_path
        d[I["ps"]] = (Q_into_s - Qleak - Qpath) * beta_eff(ps, P["beta_m"], air) / self.V_s
        d[I["Vleak"]] = Qleak
        # 先导活塞（松开侧单向阀，先导比 3）
        p_po_eff = c["p_po"] + max(pu, 0.0) / 3.0
        d[I["ypp"]] = (clip01((pr - p_po_eff) / P["dp_pp"]) - ypp) / c["tau_pp"]
        Qpp = c["V_pp"] * d[I["ypp"]]
        # 夹紧侧单向阀
        dpv = pr - (pc + self.dp_w_out)
        Qcv = self.cv_k * max(xv, 0.0) * dpv / math.sqrt(abs(dpv) + 5e3) + P["C_seat"] * dpv
        # 液动力（稳态射流力，趋于关闭）：2·Cd·π·d·sinθ·cosθ·x·Δp
        Ffl = 2 * P["Cd"] * math.pi * P["d_seat"] * math.sin(P["half_cone"]) * math.cos(P["half_cone"]) * max(xv, 0.0) * max(dpv, 0.0)
        Fv = dpv * P["A_seat"] - c["k_spr"] * (self.x0v + xv) - c["c_pop"] * vv - c.get("flow_force", 1.0) * Ffl
        if xv < 0:
            Fv += -2e6 * xv - 40.0 * vv
        elif xv > P["x_pop_max"]:
            Fv += -2e6 * (xv - P["x_pop_max"]) - 40.0 * vv
        d[I["xv"]] = vv
        d[I["vv"]] = Fv / P["m_pop"]
        d[I["pr"]] = (Qpath - Qcv - Qpp) * beta_eff(pr, P["beta_m"], air) / self.V_r
        d[I["Vcv"]] = Qcv
        # 夹紧腔、松开腔、活塞
        Qint = c["C_int"] * (pc - pu)
        yo = clip01((ypp - 0.9) / 0.1)
        Quv = P["Cd"] * P["A_uvent"] * yo * math.sqrt(2 / rho) * pu / math.sqrt(abs(pu) + 2e4)
        Vc = P["V_c"] + P["A2"] * xp
        Vu = P["V_u"] - P["A1"] * xp
        d[I["pc"]] = (Qcv - Qint - P["A2"] * vp) * beta_eff(pc, c["beta_lock"], air) / Vc
        d[I["pu"]] = (Qint + P["A1"] * vp - Quv) * beta_eff(pu, c["beta_lock"], air) / Vu
        if not self.rigid:
            d[I["xp"]] = vp
            d[I["vp"]] = (pc * P["A2"] - pu * P["A1"] - self.F0 - self.km * xp - self.cm * vp) / P["m_pist"]
        return d

    def y0(self):
        c, I = self.c, self.I
        y = np.zeros(I["n"])
        if not self.joint:
            y[I["src"]] = c["p_red"] if c["fcv_mode"] not in ("ramp", "ramp_orif") else 0.0
        y[I["pc"]] = c["p_c0"]
        y[I["pu"]] = c["p_u0"]
        # 阀芯初始压在阀座上：接触弹簧压缩量
        y[I["xv"]] = -(c["p_c0"] * self.P["A_seat"] + c["k_spr"] * self.x0v) / (2e6 + c["k_spr"])
        return y

    def atol(self):
        I = self.I
        a = np.full(I["n"], 1.0)
        if not self.joint:
            a[I["qh"]] = 1e-11
        a[I["xv"]], a[I["vv"]] = 1e-10, 1e-7
        a[I["xp"]], a[I["vp"]] = 1e-11, 1e-8
        a[I["ypp"]] = 1e-6
        for k in ("Vin", "Vleak", "Vcv", "Vrel"):
            a[I[k]] = 1e-13
        return a

    # ---------------------------------------------------------------- 运行
    def run(self, rtol=1e-6, max_step=2e-4, method="BDF"):
        """通电 → 压力升到上限附近后保持 t_hold → 断电泄放 t_vent。返回 (t, Y, info)。"""
        P, c, I = self.P, self.c, self.I
        at = self.atol()
        self.on, self.t_switch = True, 0.0
        y = self.y0()
        p_trig = c["p_red"] - 0.6 * P["pb_red"]

        def ev(t, yy):
            return yy[I["ps"]] - p_trig
        ev.terminal, ev.direction = True, 1
        s1 = solve_ivp(self.rhs, (0, c["t_max"]), y, method=method, rtol=rtol, atol=at, max_step=max_step,
                       events=ev, dense_output=True)
        segs = [s1]
        t_pl = s1.t_events[0][0] if len(s1.t_events[0]) else None
        t_off = (t_pl + c["t_hold"]) if t_pl is not None else c["t_max"]
        if t_pl is not None:
            segs.append(solve_ivp(self.rhs, (t_pl, t_off), s1.y[:, -1], method=method, rtol=rtol, atol=at,
                                  max_step=max_step, dense_output=True))
        self.on, self.t_switch = False, t_off
        segs.append(solve_ivp(self.rhs, (t_off, t_off + c["t_vent"]), segs[-1].y[:, -1], method=method, rtol=rtol,
                              atol=at, max_step=max_step, dense_output=True))
        t = np.concatenate([s.t if k == 0 else s.t[1:] for k, s in enumerate(segs)])
        Y = np.concatenate([s.y if k == 0 else s.y[:, 1:] for k, s in enumerate(segs)], axis=1)
        self.segs = segs
        yf = Y[:, -1]
        info = dict(t_plateau=t_pl, t_off=t_off, reached=t_pl is not None, ok=all(s.success for s in segs),
                    p_c_end=float(yf[I["pc"]]), p_u_end=float(yf[I["pu"]]), x_p_end=float(yf[I["xp"]]),
                    V_in=float(yf[I["Vin"]]), V_leak=float(yf[I["Vleak"]]), V_cv=float(yf[I["Vcv"]]),
                    V_rel=float(yf[I["Vrel"]]), t_pressurized=float(t_off - P["t_dv_delay"]),
                    F_bar_end=float(yf[I["pc"]] * P["A2"] - yf[I["pu"]] * P["A1"]), F_bar_0=float(self.F0),
                    nfev=int(sum(s.nfev for s in segs)))
        return t, Y, info

    def dense(self, tt):
        out = np.zeros((self.I["n"], len(tt)))
        for s in self.segs:
            m = (tt >= s.t[0]) & (tt <= s.t[-1])
            if m.any():
                out[:, m] = s.sol(tt[m])
        return out

    def knee_truth(self, t, Y):
        """真实开启时刻：阀芯升程首次超过 1 μm。返回 (t_open, p_s, p_c)。"""
        I = self.I
        m = Y[I["xv"]] > 1e-6
        if not m.any():
            return None
        k = int(np.argmax(m))
        return float(t[k]), float(Y[I["ps"], k]), float(Y[I["pc"], k])
