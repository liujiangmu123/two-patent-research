# -*- coding: utf-8 -*-
"""参数化有限元：截面组（A、I、J 线性分解）、连接刚度折减系数 κ、基础柔度（塔腿节点平动弹簧），
以及基于多模型 Ritz 基的模态降阶代理。

刚度矩阵对每组截面特性严格线性：K = Σ_g [κ_g·A_g·K^A_g + I_g·K^I_g + J_g·K^J_g] + k_v·K^s，
因此降阶矩阵可预先投影，单次特征值分析为 r×r 稠密问题（r≈60），用于 TMCMC 抽样。
"""
from __future__ import annotations

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from towerkit import sections as S
from towerkit.fem import FEModel, k_local, m_local, props_from_graph

E_STEEL = 2.06e11
G_STEEL = E_STEEL / 2.6
MASS_FACTOR = 1.15     # 节点板、螺栓等附加质量系数
ORDER = S.ANGLE_ORDER
CAT_A = np.array([S.angle(n).A for n in ORDER])
CAT_I = np.array([S.angle(n).Ix for n in ORDER])
CAT_J = np.array([S.angle(n).J for n in ORDER])
CAT_IV = np.array([S.angle(n).iv for n in ORDER])
CAT_B = np.array([S.angle(n).b for n in ORDER])


def index_of(name: str) -> int:
    return ORDER.index(S.angle(name).name)


def interp_props(u):
    """连续档位坐标 u（0…len-1）→ (A, I, J) 线性插值。"""
    u = np.clip(np.asarray(u, float), 0, len(ORDER) - 1)
    k = np.minimum(np.floor(u).astype(int), len(ORDER) - 2)
    w = u - k
    f = lambda c: (1 - w) * c[k] + w * c[k + 1]
    return f(CAT_A), f(CAT_I), f(CAT_J)


class ParamTower:
    """参数 θ = (各组截面, κ 连接刚度折减[作用于斜材/辅材轴向], log10 k_v 基础竖向刚度[N/m])。"""

    def __init__(self, g, extra_mass: dict | None = None, mass_factor: float = MASS_FACTOR, kh_ratio: float = 0.5):
        self.g = g
        self.extra_mass = dict(extra_mass or {})
        self.mass_factor = mass_factor
        self.groups = sorted(set(g.group))
        self.gi = {gr: k for k, gr in enumerate(self.groups)}
        self.egroup = np.array([self.gi[gr] for gr in g.group])
        gcat = {}
        for e, gr in enumerate(g.group):
            gcat[gr] = g.cat[e]
        self.gcat = [gcat[gr] for gr in self.groups]
        self.web = np.array([c != "main" for c in self.gcat])          # κ 作用的组
        base = g.meta.get("base_nodes") or list(np.argsort(g.nodes[:, 2])[:4])
        self.base = [int(b) for b in base]
        tmp = FEModel(g, props_from_graph(g), mass_factor=mass_factor)
        self.X, self.L, self.R, self.mi, self.mj = tmp.X, tmp.L, tmp.R, tmp.mi, tmp.mj
        self.ndof = tmp.ndof
        self.fixed = np.zeros(self.ndof, bool)
        for b in self.base:                 # 基础节点：转动固定、平动由弹簧约束
            self.fixed[6 * b + 3:6 * b + 6] = True
        self.free = np.flatnonzero(~self.fixed)
        self.ex = self.R[:, 0, :]
        self._assemble_parts(tmp)

    # ------------------------------------------------------------------ 组装分量
    def _assemble_parts(self, tmp):
        ng, nd = len(self.groups), self.ndof
        parts = {k: [[[], [], []] for _ in range(ng)] for k in ("A", "I", "J", "M")}
        for e in range(len(self.L)):
            T = tmp._T(e)
            d = tmp.dofs(e)
            r, c = np.repeat(d, 12), np.tile(d, 12)
            Lw = self.L[e]
            sec0 = S.angle(self.g.sec[e]) if self.g.sec[e] else S.angle("L63x5")
            mats = {"A": k_local(E_STEEL, G_STEEL, 1.0, 0.0, 0.0, 0.0, Lw),
                    "I": k_local(E_STEEL, G_STEEL, 0.0, 1.0, 1.0, 0.0, Lw),
                    "J": k_local(E_STEEL, G_STEEL, 0.0, 0.0, 0.0, 1.0, Lw),
                    "M": m_local(S.RHO_STEEL * self.mass_factor, 1.0, Lw, 2 * sec0.Ix / sec0.A)}
            gk = self.egroup[e]
            for k, m in mats.items():
                kg = T.T @ m @ T
                parts[k][gk][0].append(r); parts[k][gk][1].append(c); parts[k][gk][2].append(kg.ravel())
        self.P = {}
        for k in parts:
            self.P[k] = [sp.coo_matrix((np.concatenate(v), (np.concatenate(rr), np.concatenate(cc))),
                                       shape=(nd, nd)).tocsr() for rr, cc, v in parts[k]]
        ks = np.zeros(nd)
        for b in self.base:
            ks[6 * b + 0] = ks[6 * b + 1] = 0.5
            ks[6 * b + 2] = 1.0
        self.Ks = sp.diags(ks).tocsr()
        dm = np.zeros(nd)
        for nid, m in self.extra_mass.items():
            dm[6 * int(nid):6 * int(nid) + 3] += m
        self.Mx = sp.diags(dm).tocsr()

    # ------------------------------------------------------------------ 参数换算
    def group_props(self, sections=None, u=None):
        """sections: 每杆截面名列表 / {group: name}；u: 每组连续档位。返回每组 (A, I, J)。"""
        if u is not None:
            return interp_props(u)
        if sections is None:
            sections = list(self.g.sec)
        if isinstance(sections, dict):
            names = [sections[gr] for gr in self.groups]
        else:
            names = [None] * len(self.groups)
            for e, s in enumerate(sections):
                names[self.egroup[e]] = s
        idx = np.array([index_of(n) for n in names])
        return CAT_A[idx], CAT_I[idx], CAT_J[idx]

    def matrices(self, sections=None, kappa=1.0, logkv=11.0, u=None):
        A, I, J = self.group_props(sections, u)
        K = self.Ks * 10.0 ** logkv
        M = self.Mx.copy()
        for k in range(len(self.groups)):
            kap = kappa if self.web[k] else 1.0
            K = K + (kap * A[k]) * self.P["A"][k] + I[k] * self.P["I"][k] + J[k] * self.P["J"][k]
            M = M + A[k] * self.P["M"][k]
        return K.tocsr(), M.tocsr()

    def as_femodel(self, sections=None, theta=None):
        """返回 towerkit.FEModel（截面、刚度、质量与边界已按参数设置），用于荷载生成与模态叠加时程。"""
        kappa, logkv = (theta or (1.0, 11.0))[:2]
        secs = self._member_sections(sections)
        g2 = self.g.copy()
        g2.sec = secs
        fem = FEModel(g2, props_from_graph(g2), mass_factor=self.mass_factor, extra_mass=self.extra_mass)
        K, M = self.matrices(secs, kappa, logkv)
        fem._K, fem._M = K, M
        fem.fixed = self.fixed.copy()
        return fem

    def _member_sections(self, sections):
        if sections is None:
            return list(self.g.sec)
        if isinstance(sections, dict):
            return [sections[gr] for gr in self.g.group]
        return list(sections)

    # ------------------------------------------------------------------ 求解
    def modes(self, sections=None, kappa=1.0, logkv=11.0, n=10, u=None):
        K, M = self.matrices(sections, kappa, logkv, u)
        f = self.free
        Kf, Mf = K[f][:, f].tocsc(), M[f][:, f].tocsc()
        w2, v = spla.eigsh(Kf, k=n, M=Mf, sigma=0.0, which="LM")
        o = np.argsort(w2)
        phi = np.zeros((self.ndof, n)); phi[f] = v[:, o]
        return np.sqrt(np.maximum(w2[o], 0)) / 2 / np.pi, phi

    def solve_static(self, Fs, sections=None, theta=None):
        kappa, logkv = (theta or (1.0, 11.0))[:2]
        K, _ = self.matrices(sections, kappa, logkv)
        f = self.free
        lu = spla.splu(K[f][:, f].tocsc())
        Fs = np.atleast_2d(Fs)
        U = np.zeros((len(Fs), self.ndof))
        for c, F in enumerate(Fs):
            U[c, f] = lu.solve(F[f])
        return U

    def axial_forces(self, U, sections=None, theta=None):
        """杆件轴力（拉为正），N = κ·E·A/L·e_x·(u_j − u_i)。"""
        kappa = (theta or (1.0, 11.0))[0]
        A, _, _ = self.group_props(self._member_sections(sections))
        Ae = A[self.egroup] * np.where(self.web[self.egroup], kappa, 1.0)
        U = np.atleast_2d(U)
        ui = U.reshape(len(U), -1, 6)[:, :, :3]
        du = ui[:, self.mj] - ui[:, self.mi]
        return E_STEEL * Ae / self.L * np.einsum("cej,ej->ce", du, self.ex)


class ReducedModel:
    """多模型 Ritz 基模态降阶代理：Φ 由若干代表性参数点的低阶模态拼接、质量正交化截断得到。"""

    def __init__(self, pt: ParamTower, anchor_params: list, n_modes_each=24, r_max=72):
        f = pt.free
        vecs = []
        for prm in anchor_params:
            _, phi = pt.modes(n=n_modes_each, **prm)
            vecs.append(phi[f])
        V = np.hstack(vecs)
        _, M0 = pt.matrices(**{k: v for k, v in anchor_params[0].items() if k != "n"})
        Mf = M0[f][:, f]
        # 质量正交化（以首个锚点质量阵）+ 奇异值截断
        G = V.T @ (Mf @ V)
        w, Q = np.linalg.eigh(G)
        keep = w > w.max() * 1e-10
        B = V @ (Q[:, keep] / np.sqrt(w[keep]))
        if B.shape[1] > r_max:
            # 以各锚点模态投影能量排序保留
            B = B[:, ::-1][:, :r_max]
        self.pt = pt
        self.B = B
        self.r = B.shape[1]
        Bt = B.T
        P = pt.P
        self.KA = np.array([Bt @ (P["A"][k][f][:, f] @ B) for k in range(len(pt.groups))])
        self.KI = np.array([Bt @ (P["I"][k][f][:, f] @ B) for k in range(len(pt.groups))])
        self.KJ = np.array([Bt @ (P["J"][k][f][:, f] @ B) for k in range(len(pt.groups))])
        self.MA = np.array([Bt @ (P["M"][k][f][:, f] @ B) for k in range(len(pt.groups))])
        self.Ks = Bt @ (pt.Ks[f][:, f] @ B)
        self.Mx = Bt @ (pt.Mx[f][:, f] @ B)
        self.web = pt.web.astype(float)

    def eig(self, A, I, J, kappa, logkv, n=12, dofs=None):
        kapv = np.where(self.web > 0, kappa, 1.0)
        K = np.tensordot(kapv * A, self.KA, 1) + np.tensordot(I, self.KI, 1) + np.tensordot(J, self.KJ, 1) \
            + 10.0 ** logkv * self.Ks
        M = np.tensordot(A, self.MA, 1) + self.Mx
        w2, q = sla.eigh(K, M, subset_by_index=[0, n - 1])
        freq = np.sqrt(np.maximum(w2, 0)) / 2 / np.pi
        if dofs is None:
            return freq, q
        return freq, self.B[dofs] @ q

    def free_index(self, global_dofs):
        pos = -np.ones(self.pt.ndof, int)
        pos[self.pt.free] = np.arange(len(self.pt.free))
        out = pos[np.asarray(global_dofs)]
        if np.any(out < 0):
            raise ValueError("观测自由度位于约束自由度上")
        return out
