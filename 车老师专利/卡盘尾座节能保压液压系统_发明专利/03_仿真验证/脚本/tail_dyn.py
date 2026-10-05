# -*- coding: utf-8 -*-
"""尾座回路完整动态模型（毫秒—秒尺度），刚性 ODE（scipy Radau）。

状态：x 活塞位移、v 速度、p1 无杆腔、p2 有杆腔、pr1 减压阀 R1 出口管路、pr2 减压阀 R2 出口管路、
      u1/u2/u3/u4 座阀 V1/V2/V3/V4 开度（一阶 + 纯延时，延时用指令时移实现）。
用途：方案甲复位过程、方案乙脉冲微泄、M1c 补油时有杆腔失压、阶跃载荷响应、与准静态模型交叉校核。
"""
import math
import numpy as np
from scipy.integrate import solve_ivp
import hydro as H
from params import MPa, beta_eff


class TailDyn:
    def __init__(self, P, scheme="M2", x0=None, Vd=None, beta=None, F_load=None, dual=True,
                 p1=None, p2=None, Fs=None, line_V=20e-6):
        self.P = P
        self.s = scheme
        self.x0 = P["x_nom"] if x0 is None else x0
        self.Vd = P["Vd_block"] if Vd is None else Vd
        self.beta = P["beta_lock"] if beta is None else beta
        self.dual = dual
        self.Fs = P["F_s"] if Fs is None else Fs
        self.Fc = 0.8 * self.Fs
        self.p1s = P["p1_set"] if p1 is None else p1
        self.p2s = P["p_pre"] if p2 is None else p2
        self.F_load = (self.p1s * P["A1"] - self.p2s * P["A2"]) if F_load is None else F_load
        self.line_V = line_V
        self.cmd = {"V1": [], "V2": [], "V3": [], "V4": []}     # [(t_on, t_off)]
        self.p_set1, self.p_set2 = self.p1s, self.p2s
        self.R1_on, self.R2_on = True, True      # 减压阀出口接通（V0 开、换向阀在工作位）
        self.dF = lambda t: 0.0                  # 顶尖外加载荷增量（正值指向尾座，即压缩方向）
        self.k_w = None                          # 若给定则顶尖接工件弹簧（位移源 delta_fn）
        self.delta_fn = lambda t: 0.0
        self.dTdt = lambda t: 0.0
        self.rod_vent = None                     # M1c：先导打开有杆腔泄压的时间窗
        self.const_p = False                     # 无杆腔持续接减压阀（M1b）

    def u_cmd(self, name, t):
        d = self.P["delay_seat"]
        return 1.0 if any(a + d <= t < b + d for a, b in self.cmd[name]) else 0.0

    def red_flow(self, pr, pset):
        P = self.P
        if pr < pset:
            return P["red_Kq"] * (pset - pr)
        if pr > pset + P["red_db"]:
            return -P["red_Kq"] * (pr - pset - P["red_db"])
        return 0.0

    def rhs(self, t, y):
        P = self.P
        x, v, p1, p2, pr1, pr2, u1, u2, u3, u4 = y
        V1, V2 = H.chamber_volumes(x, P, self.Vd)
        b1 = beta_eff(p1, self.beta, P["air_frac"])
        b2 = beta_eff(p2, self.beta, P["air_frac"])
        bl = P["beta_hose"]
        A = P["Aseat"]
        q1 = u1 * H.orifice_q(pr1 - p1, A, P)
        q4 = u4 * H.orifice_q(pr2 - p2, A, P)
        Ao = math.pi / 4 * P["d_orif"] ** 2
        q3 = u3 * H.orifice_q(max(p1, 0.0), Ao, P)
        if self.const_p:
            q1 = H.orifice_q(pr1 - p1, A, P)
        qi = P["C_int"] * (p1 - p2) if self.dual else P["C_int"] * p1
        q2v = 0.0
        if self.rod_vent and self.rod_vent[0] <= t < self.rod_vent[1]:
            q2v = H.orifice_q(p2 - 0.05 * MPa, A, P)          # 先导打开，有杆腔经换向阀回油
        dT = self.dTdt(t)
        dp1 = b1 / V1 * (q1 - q3 - P["A1"] * v - qi + P["alpha_v"] * V1 * dT)
        if self.dual:
            dp2 = b2 / V2 * (q4 + P["A2"] * v + qi - q2v + P["alpha_v"] * V2 * dT)
        else:
            dp2 = 0.0
        qr1 = self.red_flow(pr1, self.p_set1) if self.R1_on else 0.0
        qr2 = self.red_flow(pr2, self.p_set2) if self.R2_on else 0.0
        dpr1 = bl / self.line_V * (qr1 - q1)
        dpr2 = bl / self.line_V * (qr2 - q4)
        if self.k_w is not None:
            Fw = max(0.0, self.k_w * (x - self.xc + self.delta_fn(t)))
        else:
            Fw = self.F_load + self.dF(t)
        vs = 2e-4
        ff = (self.Fc + (self.Fs - self.Fc) * math.exp(-(v / 1e-3) ** 2)) * math.tanh(v / vs) + P["c_visc"] * v
        dv = (p1 * P["A1"] - p2 * P["A2"] - Fw - ff) / P["m_pist"]
        tau = P["tau_seat"]
        du = [(self.u_cmd(n, t) - uu) / tau for n, uu in (("V1", u1), ("V2", u2), ("V3", u3), ("V4", u4))]
        return [v, dv, dp1, dp2, dpr1, dpr2] + du

    def y0(self):
        return [self.x0, 0.0, self.p1s, self.p2s if self.dual else 0.0, self.p_set1, self.p_set2, 0, 0, 0, 0]

    def run(self, t_end, y0=None, max_step=1e-3, rtol=1e-6, atol=None, t_eval=None):
        y0 = self.y0() if y0 is None else y0
        if atol is None:
            atol = [1e-10, 1e-8, 10.0, 10.0, 10.0, 10.0, 1e-6, 1e-6, 1e-6, 1e-6]
        if self.k_w is not None and not hasattr(self, "xc"):
            self.xc = y0[0] - (y0[2] * self.P["A1"] - y0[3] * self.P["A2"]) / self.k_w
        te = np.linspace(0, t_end, 2001) if t_eval is None else t_eval
        sol = solve_ivp(self.rhs, (0, t_end), y0, method="Radau", t_eval=te, max_step=max_step, rtol=rtol, atol=atol)
        if not sol.success:
            raise RuntimeError(sol.message)
        x, v, p1, p2 = sol.y[0], sol.y[1], sol.y[2], sol.y[3]
        if self.k_w is not None:
            Fw = np.maximum(0, self.k_w * (x - self.xc + np.array([self.delta_fn(t) for t in sol.t])))
        else:
            Fw = self.F_load + np.array([self.dF(t) for t in sol.t])
        Fh = p1 * self.P["A1"] - p2 * self.P["A2"]
        return {"t": sol.t, "x": x, "v": v, "p1": p1, "p2": p2, "pr1": sol.y[4], "pr2": sol.y[5],
                "u1": sol.y[6], "u3": sol.y[8], "u4": sol.y[9], "Fh": Fh, "Fw": Fw, "nfev": sol.nfev}

