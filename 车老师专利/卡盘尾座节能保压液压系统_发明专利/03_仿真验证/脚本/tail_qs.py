# -*- coding: utf-8 -*-
"""尾座保压阶段准静态模型（分钟—小时尺度）。

物理：锁闭腔油液质量守恒（内泄漏除外），压力由状态方程反求；活塞力平衡含静/动摩擦（粘滞—滑移）；
顶尖与工件端为弹簧 k_m，工件热伸长 δ(t) 为位移源；锁闭腔油温 T(t) 为体积源。
控制动作（复位/补压/泄放/溢流）相对热过程很快（<1 s），在准静态步内按终态处理；
其瞬态过程由 tail_dyn.py 的完整动态模型给出并用于校核本模型（报告 4.4 节）。

方案：
  M0   原系统：泵连续运转，三通减压阀持续接无杆腔，有杆腔通油箱（推力行为同 M1b）
  M1   常规锁闭：双液控单向阀锁两腔，有杆腔仅保留回油背压，无推力控制
  M1b  蓄能器恒压供油：三通减压阀持续接无杆腔，泵间歇
  M1c  最强现有技术组合：M1 + 无杆腔压力下限自动补油（补油时先导打开有杆腔泄压）+ 无杆腔热溢流阀上限
  M2S  本发明消融：仅无杆腔座阀锁闭 + 推力带控（有杆腔通油箱、无预压）
  M2   本发明方案甲：双腔座阀锁闭 + 有杆腔预压 + 推力带控（三通减压阀双向回复）
  M2b  本发明方案乙：双腔锁闭预压 + 下限补压 / 上限阻尼孔脉冲微泄
  M2h  M2 但锁闭腔含软管（阀块不直装缸体）
"""
import math
import numpy as np
from scipy.optimize import brentq
import hydro as H
from params import MPa

SCHEMES = ["M0", "M1s", "M1", "M1b", "M1c", "M2S", "M2", "M2b", "M2h"]
NAMES = {"M0": "M0 原系统", "M1s": "M1s 单腔锁闭+蓄能器", "M1": "M1 常规液压锁", "M1b": "M1b 蓄能器恒压", "M1c": "M1c 补油+热溢流",
         "M2S": "M2S 单腔锁闭+带控", "M2": "M2 本发明(甲)", "M2b": "M2b 本发明(乙)", "M2h": "M2h 含软管"}


class Tail:
    def __init__(self, P, scheme, x0=None, F0=None, seed=0, sensor_err=True, beta=None, Fs=None):
        self.P, self.s = P, scheme
        self.rng = np.random.default_rng(seed)
        self.F0 = P["F0"] if F0 is None else F0
        # 含软管的方案。v1.1（独立复核问题 1）：M1s（现有技术单腔锁闭，液控单向阀装在阀组上、经软管接缸）补入，
        # 与报告第 2 节和 stiffness.py 的口径一致；v1 中 M1s 误按阀块直装（β=1200、无软管容积）计算。
        HOSE = ("M0", "M1", "M1s", "M1b", "M1c", "M2h")
        self.Vd = P["Vd_hose"] + P["Vd_block"] if scheme in HOSE else P["Vd_block"]
        self.beta = (beta if beta is not None else
                     (P["beta_hose"] if scheme in HOSE else P["beta_lock"]))
        self.Fs = P["F_s"] if Fs is None else Fs
        self.Fc = 0.8 * self.Fs
        self.x0 = P["x_nom"] if x0 is None else x0
        self.dual_lock = scheme in ("M1", "M1c", "M2", "M2b", "M2h")
        self.preload = scheme in ("M2", "M2b", "M2h")
        self.const_p = scheme in ("M0", "M1b")
        A1, A2 = P["A1"], P["A2"]
        if self.preload:
            self.p2_set = P["p_pre"]
        elif scheme == "M1c":    # 补油时先导打开有杆腔泄到回油（≈0.05 MPa）再锁住
            self.p2_set = 0.05 * MPa
        elif self.dual_lock:
            self.p2_set = P["p_back"]
        else:
            self.p2_set = 0.0
        self.p1_set = (self.F0 + self.p2_set * A2) / A1
        if self.const_p:
            self.p1_set = self.F0 / A1
        # M1c 热溢流阀开启压力：按推力上限与锁闭时有杆腔压力换算（固定值）
        self.pH_relief = ((1 + P["band"]) * self.F0 + self.p2_set * A2) / A1
        # 传感器固定偏差（每台）
        e = P["acc_p"] * P["FS_p"] if sensor_err else 0.0
        self.off = self.rng.uniform(-e, e, 3)
        self.toff = self.rng.uniform(-P["dT_sensor"], P["dT_sensor"]) if sensor_err else 0.0
        self.sensor_err = sensor_err
        # 初始平衡：顶紧到位，两腔压力为设定值，摩擦为零（换向过程中已滑动）
        self.T = 0.0
        self.x = self.x0
        p1, p2 = self.p1_set, self.p2_set
        Fw0 = p1 * A1 - p2 * A2
        self.xc = self.x0 - Fw0 / P["k_m"]          # 顶尖力为零时的活塞位置
        V1, V2 = H.chamber_volumes(self.x, P, self.Vd)
        self.m1, self.m2 = H.mass_of(V1, p1, 0.0, P, self.beta), H.mass_of(V2, p2, 0.0, P, self.beta)
        self.p1, self.p2 = p1, p2
        self.delta = 0.0
        self.events = []        # (t, 类型, 进油 m3, 出油 m3)
        self.in_acc = 0.0       # 自蓄能器（或泵）取油
        self.to_tank = 0.0
        self.last_act = -1e9
        self.hist_F = []
        # ΔL 估计器
        self.dL_base, self.F_ref, self.T_ref = 0.0, None, 0.0
        self.F_ref = self.meas()[2]
        self.T_ref = self.toff
        self.x_ref = self.x
        # 压力—油温体积法（不用位移传感器）与位移传感器法所用的标定量（含标定误差）
        cal = P.get("cal_err", 0.10) if sensor_err else 0.0
        self.km_cal = P["k_m"] * (1 + self.rng.uniform(-cal, cal))
        self.beta_cal = self.beta * (1 + (self.rng.uniform(-0.2, 0.2) if sensor_err else 0.0))
        self.alpha_cal = P["alpha_v"] * (1 + (self.rng.uniform(-0.1, 0.1) if sensor_err else 0.0))
        self.dT_rel = P.get("dT_rel", 0.02) if sensor_err else 0.0       # 油温相对测量误差（同一传感器的增量误差）K
        self.x_pvt = self.x
        self._last_meas = None
        self.F0_est = self.F_ref

    # -------------------------------------------------- 物理量
    def Fw(self, x=None, delta=None):
        x = self.x if x is None else x
        delta = self.delta if delta is None else delta
        return max(0.0, self.P["k_m"] * (x - self.xc + delta))

    def pressures(self, x):
        P = self.P
        V1, V2 = H.chamber_volumes(x, P, self.Vd)
        p1 = H.pressure(self.m1, V1, self.T, P, self.beta)
        if self.dual_lock:
            p2 = H.pressure(self.m2, V2, self.T, P, self.beta)
        else:
            p2 = 0.0
        if self.const_p:          # 三通减压阀持续接通：p1 保持在 [set, set+db]
            p1 = min(max(p1, self.p1_set), self.p1_set + P["red_db"])
        return p1, p2

    def imbalance(self, x):
        p1, p2 = self.pressures(x)
        return p1 * self.P["A1"] - p2 * self.P["A2"] - self.Fw(x)

    def equilibrate(self):
        """粘滞—滑移：|不平衡力|≤F_s 时活塞不动；否则滑移到不平衡力 = ±F_c 处。"""
        f = self.imbalance(self.x)
        if abs(f) <= self.Fs:
            self.p1, self.p2 = self.pressures(self.x)
            if self.const_p:      # 油温变化时减压阀进出油维持 p1，计入取油/回油
                V1, _ = H.chamber_volumes(self.x, self.P, self.Vd)
                mn = H.mass_of(V1, self.p1, self.T, self.P, self.beta)
                dm = mn - self.m1
                self.in_acc += max(dm, 0.0)
                self.to_tank += max(-dm, 0.0)
                self.m1 = mn
            return
        sgn = 1.0 if f > 0 else -1.0
        g = lambda x: self.imbalance(x) - sgn * self.Fc
        step = 20e-6 * sgn
        a, b = self.x, self.x + step
        for _ in range(200):
            if g(b) * sgn <= 0:
                break
            a, b = b, b + step
            step *= 1.6
        xn = brentq(g, min(a, b), max(a, b), xtol=1e-10)
        if self.const_p:          # 恒压供油时活塞移动引起减压阀进出油
            V1o, _ = H.chamber_volumes(self.x, self.P, self.Vd)
        self.x = xn
        self.p1, self.p2 = self.pressures(self.x)
        if self.const_p:
            V1, _ = H.chamber_volumes(self.x, self.P, self.Vd)
            mn = H.mass_of(V1, self.p1, self.T, self.P, self.beta)
            dm = mn - self.m1
            self.in_acc += max(dm, 0.0)
            self.to_tank += max(-dm, 0.0)
            self.m1 = mn

    # -------------------------------------------------- 测量
    def meas(self):
        P = self.P
        n = P["noise_p"] * P["FS_p"] if self.sensor_err else 0.0
        p1m = self.p1 + self.off[0] + self.rng.normal(0, n)
        p2m = (self.p2 + self.off[1] + self.rng.normal(0, n)) if self.dual_lock else 0.0
        return p1m, p2m, p1m * P["A1"] - p2m * P["A2"]

    # -------------------------------------------------- 控制动作
    def _set_chamber(self, i, p_target):
        """把第 i 腔压力置为 p_target（经减压阀/溢流阀/阻尼孔），活塞同步滑移到新平衡。"""
        P = self.P
        # 求新平衡位置：腔 i 压力固定为 p_target，另一腔质量守恒
        def f(x):
            V1, V2 = H.chamber_volumes(x, P, self.Vd)
            p1 = p_target if i == 1 else H.pressure(self.m1, V1, self.T, P, self.beta)
            p2 = p_target if i == 2 else (H.pressure(self.m2, V2, self.T, P, self.beta) if self.dual_lock else 0.0)
            return p1 * P["A1"] - p2 * P["A2"] - self.Fw(x)
        f0 = f(self.x)
        if abs(f0) > self.Fs:
            sgn = 1.0 if f0 > 0 else -1.0
            g = lambda x: f(x) - sgn * self.Fc
            a, b, step = self.x, self.x + 20e-6 * sgn, 20e-6 * sgn
            for _ in range(200):
                if g(b) * sgn <= 0:
                    break
                a, b = b, b + step
                step *= 1.6
            self.x = brentq(g, min(a, b), max(a, b), xtol=1e-10)
        V1, V2 = H.chamber_volumes(self.x, P, self.Vd)
        if i == 1:
            mn = H.mass_of(V1, p_target, self.T, P, self.beta)
            dm, self.m1 = mn - self.m1, mn
        else:
            mn = H.mass_of(V2, p_target, self.T, P, self.beta)
            dm, self.m2 = mn - self.m2, mn
        self.in_acc += max(dm, 0.0)
        self.to_tank += max(-dm, 0.0)
        self.p1, self.p2 = self.pressures(self.x)
        return dm

    def reset_3way(self, i, p_set):
        """三通减压阀双向回复：低于设定进油至 p_set，高于 p_set+db 溢流至 p_set+db，其间不动作。"""
        p = self.p1 if i == 1 else self.p2
        db = self.P["red_db"]
        if self.P.get("rev_center", False):       # 修订：减压阀设定下移 db/2，使回复窗口对称于设定值
            p_set = p_set - db / 2
        if p < p_set:
            return self._set_chamber(i, p_set)
        if p > p_set + db:
            return self._set_chamber(i, p_set + db)
        return 0.0

    def control(self, t, dt):
        P, s = self.P, self.s
        p1m, p2m, Fm = self.meas()
        if self.dual_lock:
            Tm = self.T + self.toff + (self.rng.normal(0, self.dT_rel) if self.sensor_err else 0.0)
            self.update_pvt(p1m, p2m, Tm)
        self.hist_F.append(Fm)
        nwin = max(1, int(round(P["t_filter"] / dt)))
        Ff = float(np.mean(self.hist_F[-nwin:]))
        if self.F_ref is None:
            self.F_ref = Ff
        FL, FH = (1 - P["band"]) * self.F0, (1 + P["band"]) * self.F0
        act = None
        if s in ("M2", "M2h", "M2S", "M2b"):
            urgent = Fm > P["F_safe"] * self.F0
            low_p2 = self.dual_lock and p2m < 0.5 * self.p2_set
            if (Ff < FL or Ff > FH or low_p2 or urgent) and (t - self.last_act >= P["t_min_gap"] or urgent):
                Fb = Ff
                if s in ("M2", "M2h", "M2S"):
                    dm1 = self.reset_3way(1, self.p1_set)
                    dm2 = self.reset_3way(2, self.p2_set) if self.dual_lock else 0.0
                    act = ("复位", dm1, dm2)
                else:   # M2b 方案乙：有杆腔经 V4 回复预压；无杆腔低于设定补压，推力偏高时阻尼孔脉冲微泄
                    dm2 = self.reset_3way(2, self.p2_set)
                    if Ff > FH or urgent:
                        dm1 = self.pulse_release(target=self.F0)
                        act = ("微泄", dm1, dm2)
                    else:
                        dm1 = self._set_chamber(1, self.p1_set) if self.p1 < self.p1_set else 0.0
                        if self.p1 * P["A1"] - self.p2 * P["A2"] > FH:
                            dm1 += self.pulse_release(target=self.F0)
                        act = ("补压", dm1, dm2)
                self.last_act = t
                self.events.append((t, act[0], act[1], act[2]))
                # ΔL 估计：动作前的增量计入基值；动作中活塞位移由推力变化/k_m 推算（工件伸长不变）
                Fa = self.meas()[2]
                self.dL_base = self.dL_estimate(Fb, t, update=False)
                self.x_pvt += (Fa - Fb) / self.km_cal
                self.hist_F = [Fa]
                self.F_ref = Fa
                self.T_ref = self.T + self.toff
                self._last_meas = None
        elif s == "M1s":
            # 现有技术（CN107559250A 类）：液控单向阀锁无杆腔，有杆腔通油箱，压力继电器低于下限补油，无上限动作
            p_low = (1 - P["band"]) * self.F0 / P["A1"]
            if p1m < p_low and t - self.last_act >= P["t_min_gap"]:
                dm1 = self._set_chamber(1, self.p1_set)
                self.last_act = t
                self.events.append((t, "补油", dm1, 0.0))
        elif s == "M1c":
            p_switch_low = ((1 - P["band"]) * self.F0 + self.p2_set * P["A2"]) / P["A1"]
            if self.p1 > self.pH_relief:
                dm = self._set_chamber(1, self.pH_relief)        # 热溢流阀被动限压（按 p1 动作）
                self.events.append((t, "溢流", dm, 0.0))
            elif p1m < p_switch_low and t - self.last_act >= P["t_min_gap"]:
                # 补油：换向阀前进位 → 无杆腔进油至设定，先导打开有杆腔 → 泄至回油压力
                dm2 = self._set_chamber(2, 0.05 * MPa)
                dm1 = self._set_chamber(1, self.p1_set)
                self.last_act = t
                self.events.append((t, "补油", dm1, dm2))
        return Ff

    def pulse_release(self, target):
        """方案乙：V3 + 阻尼孔脉冲微泄，每脉冲后测量，直到推力 ≤ target（最多 50 个脉冲）。"""
        P = self.P
        A = math.pi / 4 * P["d_orif"] ** 2
        tot = 0.0
        for _ in range(50):
            q = H.orifice_q(self.p1, A, P)
            dv = q * (P["t_pulse"] + P["tau_seat"])          # 开启+关闭过渡折合
            self.m1 -= dv
            tot -= dv
            self.equilibrate()
            if self.p1 * P["A1"] - self.p2 * P["A2"] <= target:
                break
        self.to_tank += -tot
        return tot

    def dL_estimate(self, Fm, t, update=True):
        """估计法一（仅压力+油温推力换算）：ΔL = 基值 + (F − F_ref − S_T·(T − T_ref)) / K_w。不能区分内泄漏。"""
        P = self.P
        Kw = H.K_series(self.x, P, self.Vd, self.beta_cal, self.beta_cal, self.dual_lock)
        ST = H.thermal_N_per_K(self.x, P, self.Vd, self.beta_cal, self.dual_lock)
        Tm = self.T + self.toff
        return self.dL_base + ((Fm - self.F_ref) - ST * (Tm - self.T_ref)) / Kw

    def update_pvt(self, p1m, p2m, Tm):
        """估计法二（双腔压力—油温体积法）：内泄漏只在两腔间转移油液，两腔占据体积之和对其不敏感，
        (A1−A2)dx = V1(α dT − dp1/β) + V2(α dT − dp2/β)，由此积分得活塞位移，无需位移传感器。"""
        P = self.P
        if self._last_meas is None:
            self._last_meas = (p1m, p2m, Tm)
            return
        q1, q2, Tq = self._last_meas
        V1, V2 = H.chamber_volumes(self.x_pvt, P, self.Vd)
        a, b = self.alpha_cal, self.beta_cal
        dT = Tm - Tq
        dx = (V1 * (a * dT - (p1m - q1) / b) + V2 * (a * dT - (p2m - q2) / b)) / (P["A1"] - P["A2"])
        self.x_pvt += dx
        self._last_meas = (p1m, p2m, Tm)

    def dL_all(self, Fm):
        """返回三种伸长估计（µm）：仅压力法、压力—油温体积法、位移传感器法。"""
        P = self.P
        e1 = self.dL_estimate(Fm, 0) * 1e6
        e2 = ((Fm - self.F0_est) / self.km_cal - (self.x_pvt - self.x_ref)) * 1e6 if self.dual_lock else float("nan")
        xm = self.x + (self.rng.normal(0, 0.5e-6) if self.sensor_err else 0.0)       # 缸内位移传感器 1 µm 分辨率
        e3 = ((Fm - self.F0_est) / self.km_cal - (xm - self.x_ref)) * 1e6
        return e1, e2, e3

    # -------------------------------------------------- 主循环
    def run(self, t_end, dt, delta_fn, temp_fn, leak_mult=1.0, record_every=1):
        P = self.P
        out = {k: [] for k in ("t", "delta_um", "T_K", "x_mm", "p1_MPa", "p2_MPa", "F_N", "Fest_N",
                               "dL1_um", "dL2_um", "dL3_um")}
        n = int(round(t_end / dt))
        for k in range(n + 1):
            t = k * dt
            if k > 0:
                # 内泄漏（无杆腔→有杆腔或油箱），座阀泄漏（按零泄漏处理，取 1e-4 cm3/min/MPa）
                Ci = P["C_int"] * leak_mult
                if self.dual_lock:
                    q = Ci * (self.p1 - self.p2)
                    self.m1 -= q * dt
                    self.m2 += q * dt
                elif not self.const_p:
                    self.m1 -= Ci * self.p1 * dt
                cs = 1e-4 * 1e-6 / 60 / MPa
                self.m1 -= cs * max(self.p1, 0) * dt
                if self.dual_lock:
                    self.m2 -= cs * max(self.p2, 0) * dt
                self.delta = delta_fn(t)
                self.T = temp_fn(t)
                self.equilibrate()
            Ff = self.control(t, dt) if k > 0 else self.meas()[2]
            if k % record_every == 0:
                out["t"].append(t)
                out["delta_um"].append(self.delta * 1e6)
                out["T_K"].append(self.T)
                out["x_mm"].append(self.x * 1e3)
                out["p1_MPa"].append(self.p1 / MPa)
                out["p2_MPa"].append(self.p2 / MPa)
                out["F_N"].append(self.Fw())
                out["Fest_N"].append(Ff)
                if self.s in ("M2", "M2b", "M2h", "M2S"):
                    e1, e2, e3 = self.dL_all(Ff)
                else:
                    e1 = e2 = e3 = float("nan")
                out["dL1_um"].append(e1)
                out["dL2_um"].append(e2)
                out["dL3_um"].append(e3)
        F = np.array(out["F_N"])
        res = {
            "方案": self.s, "名称": NAMES[self.s],
            "推力最大N": float(F.max()), "推力最小N": float(F.min()),
            "最大正偏差%": float(100 * (F.max() - self.F0) / self.F0),
            "最大负偏差%": float(100 * (F.min() - self.F0) / self.F0),
            "动作次数": len(self.events),
            "动作明细": {k: sum(1 for e in self.events if e[1] == k) for k in set(e[1] for e in self.events)},
            "取油cm3": self.in_acc * 1e6, "回油箱cm3": self.to_tank * 1e6,
            "终了p2_MPa": self.p2 / MPa, "最低p2_MPa": float(min(out["p2_MPa"])),
        }
        return res, out


def ramp_growth(dmax, tau):
    return lambda t: dmax * (1 - math.exp(-t / tau))


def linear_temp(rate_K_per_s):
    return lambda t: rate_K_per_s * t
