# -*- coding: utf-8 -*-
"""三维空间梁单元有限元：静力（含支座位移、温度作用）、模态、Newmark/模态叠加时程、规范验算、影响矩阵。

每节点 6 自由度 (ux, uy, uz, rx, ry, rz)；单元为 Euler-Bernoulli 梁（可选只保留轴向刚度的杆单元）。
角钢截面取平行肢轴惯性矩 Ix 作两个弯曲方向的惯性矩（格构塔整体响应由轴向刚度控制，该近似误差很小）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from . import sections as S
from .graph import TrussGraph


def _frame(p1, p2):
    ex = p2 - p1
    L = float(np.linalg.norm(ex))
    ex = ex / L
    ref = np.array([0.0, 0.0, 1.0]) if abs(ex[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    ez = np.cross(ex, ref); ez /= np.linalg.norm(ez)
    ey = np.cross(ez, ex)
    return L, np.vstack([ex, ey, ez])


def k_local(E, G, A, Iy, Iz, J, L, truss=False):
    k = np.zeros((12, 12))
    ea = E * A / L
    k[0, 0] = k[6, 6] = ea; k[0, 6] = k[6, 0] = -ea
    if truss:
        return k
    gj = G * J / L
    k[3, 3] = k[9, 9] = gj; k[3, 9] = k[9, 3] = -gj
    # 绕局部 z 弯曲（v, θz：1,5,7,11）
    a, b, c, d = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, 4 * E * Iz / L, 2 * E * Iz / L
    for (i, j, v) in ((1, 1, a), (1, 5, b), (1, 7, -a), (1, 11, b), (5, 5, c), (5, 7, -b), (5, 11, d),
                      (7, 7, a), (7, 11, -b), (11, 11, c)):
        k[i, j] = k[j, i] = v
    # 绕局部 y 弯曲（w, θy：2,4,8,10）
    a, b, c, d = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, 4 * E * Iy / L, 2 * E * Iy / L
    for (i, j, v) in ((2, 2, a), (2, 4, -b), (2, 8, -a), (2, 10, -b), (4, 4, c), (4, 8, b), (4, 10, d),
                      (8, 8, a), (8, 10, b), (10, 10, c)):
        k[i, j] = k[j, i] = v
    return k


def m_local(rho, A, L, Ip, consistent=True):
    m = rho * A * L
    M = np.zeros((12, 12))
    if not consistent:
        for d in (0, 1, 2, 6, 7, 8):
            M[d, d] = m / 2
        rot = m * L ** 2 / 420.0
        for d in (3, 4, 5, 9, 10, 11):
            M[d, d] = rot if d not in (3, 9) else m * Ip / A / 2
        return M
    M[0, 0] = M[6, 6] = m / 3; M[0, 6] = M[6, 0] = m / 6
    jx = m * Ip / A
    M[3, 3] = M[9, 9] = jx / 3; M[3, 9] = M[9, 3] = jx / 6
    f = m / 420.0
    for (i, j, v) in ((1, 1, 156), (1, 5, 22 * L), (1, 7, 54), (1, 11, -13 * L), (5, 5, 4 * L * L), (5, 7, 13 * L),
                      (5, 11, -3 * L * L), (7, 7, 156), (7, 11, -22 * L), (11, 11, 4 * L * L)):
        M[i, j] = M[j, i] = f * v
    for (i, j, v) in ((2, 2, 156), (2, 4, -22 * L), (2, 8, 54), (2, 10, 13 * L), (4, 4, 4 * L * L), (4, 8, -13 * L),
                      (4, 10, -3 * L * L), (8, 8, 156), (8, 10, 22 * L), (10, 10, 4 * L * L)):
        M[i, j] = M[j, i] = f * v
    return M


@dataclass
class ElemProps:
    E: np.ndarray
    G: np.ndarray
    A: np.ndarray
    I: np.ndarray
    J: np.ndarray
    rho: np.ndarray
    alpha: np.ndarray
    b: np.ndarray
    iv: np.ndarray
    fy: np.ndarray
    f: np.ndarray


def props_from_graph(g: TrussGraph, stiff_scale=None) -> ElemProps:
    n = g.n_members
    arr = {k: np.zeros(n) for k in ("E", "G", "A", "I", "J", "rho", "alpha", "b", "iv", "fy", "f")}
    for e in range(n):
        a = S.angle(g.sec[e]) if g.sec[e] else S.angle("L63x5")
        st = S.steel(g.mat[e] or "Q235")
        arr["E"][e], arr["G"][e], arr["A"][e], arr["I"][e], arr["J"][e] = st.E, st.G, a.A, a.Ix, a.J
        arr["rho"][e], arr["alpha"][e], arr["b"][e], arr["iv"][e] = st.rho, st.alpha, a.b, a.iv
        arr["fy"][e], arr["f"][e] = st.fy, st.f
    if stiff_scale is not None:
        arr["E"] *= stiff_scale; arr["G"] *= stiff_scale
    return ElemProps(**arr)


class FEModel:
    """由 TrussGraph 建立的空间梁有限元模型。"""

    def __init__(self, g: TrussGraph, props: ElemProps | None = None, mass_factor: float = 1.15,
                 truss: bool = False, consistent_mass: bool = True, extra_mass: dict | None = None):
        self.g = g
        self.X = np.asarray(g.nodes, float)
        self.mi, self.mj = g.ends()
        self.p = props or props_from_graph(g)
        self.mass_factor = mass_factor
        self.truss = truss
        self.consistent = consistent_mass
        self.extra_mass = extra_mass or {}
        self.n = len(self.X)
        self.ndof = 6 * self.n
        self.L = np.zeros(g.n_members)
        self.R = np.zeros((g.n_members, 3, 3))
        for e in range(g.n_members):
            self.L[e], self.R[e] = _frame(self.X[self.mi[e]], self.X[self.mj[e]])
        self.fixed = np.zeros(self.ndof, bool)
        self._K = None
        self._M = None

    # ---------------------------------------------------------------- 组装
    def _T(self, e):
        T = np.zeros((12, 12))
        for b in range(4):
            T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = self.R[e]
        return T

    def dofs(self, e):
        a, b = self.mi[e], self.mj[e]
        return np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]

    def K(self):
        if self._K is None:
            rows, cols, vals = [], [], []
            p = self.p
            for e in range(len(self.L)):
                T = self._T(e)
                kl = k_local(p.E[e], p.G[e], p.A[e], p.I[e], p.I[e], p.J[e], self.L[e], self.truss)
                kg = T.T @ kl @ T
                d = self.dofs(e)
                rows.append(np.repeat(d, 12)); cols.append(np.tile(d, 12)); vals.append(kg.ravel())
            K = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                              shape=(self.ndof, self.ndof)).tocsr()
            if self.truss:   # 杆单元：给转动自由度加微小刚度防奇异
                K = K + sp.diags(np.tile([0, 0, 0, 1.0, 1.0, 1.0], self.n))
            self._K = K
        return self._K

    def M(self):
        if self._M is None:
            rows, cols, vals = [], [], []
            p = self.p
            for e in range(len(self.L)):
                T = self._T(e)
                Ip = 2 * p.I[e]
                ml = m_local(p.rho[e] * self.mass_factor, p.A[e], self.L[e], Ip, self.consistent)
                mg = T.T @ ml @ T
                d = self.dofs(e)
                rows.append(np.repeat(d, 12)); cols.append(np.tile(d, 12)); vals.append(mg.ravel())
            M = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                              shape=(self.ndof, self.ndof)).tocsr()
            if self.extra_mass:
                dm = np.zeros(self.ndof)
                for nid, m in self.extra_mass.items():
                    dm[6 * nid:6 * nid + 3] += m
                M = M + sp.diags(dm)
            self._M = M
        return self._M

    def total_mass(self) -> float:
        p = self.p
        return float(np.sum(p.rho * self.mass_factor * p.A * self.L) + sum(self.extra_mass.values()))

    # ---------------------------------------------------------------- 边界
    def fix_nodes(self, nodes, dofs=(0, 1, 2, 3, 4, 5)):
        for nd in np.atleast_1d(nodes):
            for d in dofs:
                self.fixed[6 * int(nd) + d] = True
        return self

    def fix_base(self, pinned=False):
        base = self.g.meta.get("base_nodes") or list(np.argsort(self.X[:, 2])[:4])
        return self.fix_nodes(base, (0, 1, 2) if pinned else (0, 1, 2, 3, 4, 5))

    # ---------------------------------------------------------------- 荷载向量
    def thermal_load(self, dT: np.ndarray, dTgrad: np.ndarray | None = None, depth: np.ndarray | None = None):
        """均匀温升 dT（每杆）与沿局部 y 的截面温差 dTgrad（每杆，K）引起的等效节点荷载。"""
        F = np.zeros(self.ndof)
        p = self.p
        for e in range(len(self.L)):
            fl = np.zeros(12)
            n0 = p.E[e] * p.A[e] * p.alpha[e] * dT[e]
            fl[0], fl[6] = -n0, n0
            if dTgrad is not None and dTgrad[e] != 0 and not self.truss:
                h = depth[e] if depth is not None else p.b[e]
                m0 = p.E[e] * p.I[e] * p.alpha[e] * dTgrad[e] / h
                fl[5], fl[11] = -m0, m0
            F[self.dofs(e)] += self._T(e).T @ fl
        return F

    def gravity_load(self, g_acc=9.81):
        d = np.zeros(self.ndof)
        d[2::6] = -g_acc
        return self.M() @ d

    # ---------------------------------------------------------------- 求解
    def solve_static(self, F=None, prescribed: dict | None = None):
        """F：节点荷载向量；prescribed：{dof: 位移}（支座位移，dof 须为约束自由度）。返回全自由度位移。"""
        F = np.zeros(self.ndof) if F is None else np.asarray(F, float)
        u = np.zeros(self.ndof)
        if prescribed:
            for d, v in prescribed.items():
                u[d] = v
        fr = ~self.fixed
        K = self.K()
        rhs = F[fr] - K[fr][:, self.fixed] @ u[self.fixed]
        u[fr] = spla.spsolve(K[fr][:, fr].tocsc(), rhs)
        return u

    def factorize(self):
        fr = ~self.fixed
        self._lu = spla.splu(self.K()[fr][:, fr].tocsc())
        return self._lu

    def solve_many(self, Fs, prescribed_list=None):
        """多工况静力（复用 LU 分解）。Fs: (ncase, ndof)。"""
        fr = ~self.fixed
        lu = getattr(self, "_lu", None) or self.factorize()
        K = self.K()
        U = np.zeros((len(Fs), self.ndof))
        for c, F in enumerate(Fs):
            u = np.zeros(self.ndof)
            if prescribed_list and prescribed_list[c]:
                for d, v in prescribed_list[c].items():
                    u[d] = v
            rhs = F[fr] - K[fr][:, self.fixed] @ u[self.fixed]
            u[fr] = lu.solve(rhs)
            U[c] = u
        return U

    def member_forces(self, u, dT=None, dTgrad=None, depth=None):
        """返回每杆局部端力 (M,12)，以及轴力 N（拉为正）。"""
        p = self.p
        out = np.zeros((len(self.L), 12))
        for e in range(len(self.L)):
            T = self._T(e)
            kl = k_local(p.E[e], p.G[e], p.A[e], p.I[e], p.I[e], p.J[e], self.L[e], self.truss)
            fl = kl @ (T @ u[self.dofs(e)])
            if dT is not None:
                n0 = p.E[e] * p.A[e] * p.alpha[e] * dT[e]
                fl[0] += n0; fl[6] -= n0
            if dTgrad is not None and dTgrad[e] != 0 and not self.truss:
                h = depth[e] if depth is not None else p.b[e]
                m0 = p.E[e] * p.I[e] * p.alpha[e] * dTgrad[e] / h
                fl[5] += m0; fl[11] -= m0
            out[e] = fl
        N = out[:, 6]
        return out, N

    def modes(self, n=10, sigma=0.0):
        fr = ~self.fixed
        K = self.K()[fr][:, fr].tocsc()
        M = self.M()[fr][:, fr].tocsc()
        w2, v = spla.eigsh(K, k=n, M=M, sigma=sigma, which="LM")
        idx = np.argsort(w2)
        w2, v = w2[idx], v[:, idx]
        phi = np.zeros((self.ndof, n))
        phi[fr] = v
        # 质量归一化
        mm = np.einsum("ij,ij->j", v, M @ v)
        phi /= np.sqrt(mm)
        freq = np.sqrt(np.maximum(w2, 0)) / (2 * np.pi)
        return freq, phi

    def rayleigh(self, zeta, f1, f2):
        w1, w2 = 2 * np.pi * f1, 2 * np.pi * f2
        a = 2 * zeta * w1 * w2 / (w1 + w2)
        b = 2 * zeta / (w1 + w2)
        return a, b

    def newmark(self, F_t: np.ndarray, dt: float, zeta=0.02, fband=(1.0, 10.0), out_dofs=None,
                beta=0.25, gamma=0.5):
        """直接积分（平均加速度法）。F_t: (nt, ndof)。返回 (位移, 加速度)，仅 out_dofs。"""
        fr = np.flatnonzero(~self.fixed)
        K = self.K()[fr][:, fr].tocsc(); M = self.M()[fr][:, fr].tocsc()
        a_r, b_r = self.rayleigh(zeta, *fband)
        C = a_r * M + b_r * K
        a0, a1 = 1 / (beta * dt ** 2), gamma / (beta * dt)
        a2, a3 = 1 / (beta * dt), 1 / (2 * beta) - 1
        a4, a5 = gamma / beta - 1, dt / 2 * (gamma / beta - 2)
        lu = spla.splu((K + a0 * M + a1 * C).tocsc())
        nt = len(F_t)
        out_dofs = np.arange(self.ndof) if out_dofs is None else np.asarray(out_dofs)
        pos = {d: i for i, d in enumerate(fr)}
        sel = np.array([pos[d] for d in out_dofs])
        u = np.zeros(len(fr)); v = np.zeros(len(fr))
        acc = spla.splu(M).solve(F_t[0][fr] - C @ v - K @ u)
        U = np.zeros((nt, len(sel))); Acc = np.zeros((nt, len(sel)))
        U[0], Acc[0] = u[sel], acc[sel]
        for k in range(1, nt):
            rhs = F_t[k][fr] + M @ (a0 * u + a2 * v + a3 * acc) + C @ (a1 * u + a4 * v + a5 * acc)
            un = lu.solve(rhs)
            an = a0 * (un - u) - a2 * v - a3 * acc
            v = v + dt * ((1 - gamma) * acc + gamma * an)
            u, acc = un, an
            U[k], Acc[k] = u[sel], acc[sel]
        return U, Acc

    def modal_response(self, F_t: np.ndarray, dt: float, n_modes=12, zeta=0.02, out_dofs=None, return_q=False):
        """模态叠加（各阶 SDOF 精确递推，Nigam-Jennings 分段线性荷载）。返回 (位移, 加速度, freq, phi)。

        zeta 可为标量或长度 n_modes 的逐阶阻尼比数组；return_q=True 时额外返回模态坐标 (q, qd, qdd)。
        """
        from scipy.linalg import expm
        freq, phi = self.modes(n_modes)
        P = F_t @ phi                                 # (nt, n) 模态力
        w = 2 * np.pi * freq
        nm = len(w)
        zeta = np.broadcast_to(np.asarray(zeta, float), (nm,))
        Ad = np.zeros((nm, 2, 2)); Bd = np.zeros((nm, 2))
        for r in range(nm):                           # 状态空间零阶保持离散化（无条件稳定、无相位误差积累）
            Ac = np.array([[0.0, 1.0], [-w[r] ** 2, -2 * zeta[r] * w[r]]])
            Ad[r] = expm(Ac * dt)
            Bd[r] = np.linalg.solve(Ac, (Ad[r] - np.eye(2)) @ np.array([0.0, 1.0]))
        nt = len(F_t)
        x = np.zeros((nm, 2))
        q = np.zeros((nt, nm)); qd = np.zeros_like(q)
        for k in range(nt - 1):
            pk = 0.5 * (P[k] + P[k + 1])
            x = np.einsum("rij,rj->ri", Ad, x) + Bd * pk[:, None]
            q[k + 1], qd[k + 1] = x[:, 0], x[:, 1]
        qdd = P - 2 * zeta * w * qd - w ** 2 * q
        out_dofs = np.arange(self.ndof) if out_dofs is None else np.asarray(out_dofs)
        if return_q:
            return q @ phi[out_dofs].T, qdd @ phi[out_dofs].T, freq, phi, (q, qd, qdd)
        return q @ phi[out_dofs].T, qdd @ phi[out_dofs].T, freq, phi

    # ---------------------------------------------------------------- 规范验算与影响矩阵
    def check_members(self, N: np.ndarray, mu: float = 1.0):
        """返回长细比、稳定系数、应力比（受压按 φAf，受拉按 Af）。"""
        p = self.p
        lam = mu * self.L / p.iv
        phi = np.array([S.phi_b(l, fy) for l, fy in zip(lam, p.fy)])
        ratio = np.where(N < 0, -N / (phi * p.A * p.f), N / (p.A * p.f))
        return {"lambda": lam, "phi": phi, "ratio": ratio}

    def influence_matrix(self, cases: list, out_nodes, comps=(0, 1, 2)):
        """cases: [(F, prescribed_dict)]；返回 (len(out_nodes)*len(comps), ncase) 位移影响矩阵。"""
        Fs = np.array([c[0] if c[0] is not None else np.zeros(self.ndof) for c in cases])
        U = self.solve_many(Fs, [c[1] for c in cases])
        rows = [6 * int(nd) + cc for nd in np.atleast_1d(out_nodes) for cc in comps]
        return U[:, rows].T, U

    def node_disp(self, u, nodes=None):
        U = u.reshape(-1, 6)[:, :3]
        return U if nodes is None else U[np.asarray(nodes)]
