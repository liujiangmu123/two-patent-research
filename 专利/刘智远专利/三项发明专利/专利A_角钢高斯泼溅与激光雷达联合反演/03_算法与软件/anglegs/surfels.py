# -*- coding: utf-8 -*-
"""确定性生成函数：桁架参数 → 角钢两肢面元高斯条带（可被 autograd 求导）。

约定（与 towerkit.lidar 几何一致）：杆件 e=(i,j)，轴向 u=(v_j−v_i)/L；参考向量 r_e 在初始化时确定并保持常量
（塔身取指向塔心的水平向量，与杆轴近平行时取竖直/横向向量）；p=normalize(r−(r·u)u)，q=u×p；
n1=cosφ·p+sinφ·q，n2=u×n1；肢背棱线 = 节点连线 + δ1·n1 + δ2·n2；两肢分别沿 n1、n2 伸出肢宽 b。

第 (k,m,p) 个面元高斯（k=1..K 沿轴、m=1,2 肢、p=1..P 列）：
    μ = v_i + ((k−½)/K)(v_j−v_i) + δ1·n1 + δ2·n2 + ((p−½)/P)·b·n_m
    切向轴 (u, n_m)，切向尺度 (c_a·L/(2K), c_w·b/(2P))，不透明度 α = α0·σ(logit)。
面元高斯的中心、尺度、朝向、不透明度全部由桁架参数确定，不作为独立优化变量；相连杆件共享节点。

消融用基元：kind="cylinder" 时每根杆件为 4 列绕轴均布、半径 b/2 的圆管面元（GaussianPlant 式圆柱基元）。
"""
from __future__ import annotations

from dataclasses import dataclass

import autograd.numpy as anp
import numpy as np

ALPHA0 = 0.98          # 基准不透明度（<1 以保证 log(1−h) 有界）
C_AXIAL = 1.10         # 轴向尺度系数：相邻面元重叠，条带连续
C_WIDTH = 0.92         # 横向尺度系数：P=2 时使条带遮挡率剖面的等效宽度≈肢宽（2–8 像素肢宽范围内偏差≤4%，见测试）


def cross(a, b):
    """逐行叉积（autograd 安全）。"""
    return anp.stack([a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1],
                      a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2],
                      a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]], axis=1)


def rowdot(a, b):
    return anp.sum(a * b, axis=1)


def sigmoid(x):
    return 0.5 * (anp.tanh(0.5 * x) + 1.0)


def ref_vectors(nodes, mi, mj, center_xy=(0.0, 0.0)):
    """每杆固定参考向量 r_e：指向塔心的水平向量；与杆轴夹角过小时改用竖直，再退化为 x 轴。"""
    nodes = np.asarray(nodes, float)
    a, b = nodes[mi], nodes[mj]
    u = b - a
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    mid = 0.5 * (a + b)
    toc = np.zeros_like(mid)
    toc[:, 0] = center_xy[0] - mid[:, 0]
    toc[:, 1] = center_xy[1] - mid[:, 1]
    nt = np.linalg.norm(toc, axis=1)
    r = np.where(nt[:, None] > 1e-6, toc / np.maximum(nt, 1e-9)[:, None], np.array([1.0, 0.0, 0.0]))
    for cand in (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])):
        perp = r - np.sum(r * u, 1, keepdims=True) * u
        bad = np.linalg.norm(perp, axis=1) < 0.3
        if not bad.any():
            break
        r[bad] = cand
    return r


def frames(vi, vj, r, phi):
    """局部标架 u, n1, n2 与杆长 L（autograd 安全）。"""
    a = vj - vi
    L = anp.sqrt(rowdot(a, a))
    u = a / L[:, None]
    p = r - rowdot(r, u)[:, None] * u
    p = p / anp.sqrt(rowdot(p, p))[:, None]
    q = cross(u, p)
    n1 = anp.cos(phi)[:, None] * p + anp.sin(phi)[:, None] * q
    n2 = cross(u, n1)
    return u, n1, n2, L


def phi_from_legs(u, r, w1, w2):
    """由真值两肢方向反求 φ：选使 u×n1=n2 成立的那一肢作 n1。"""
    u, r, w1, w2 = map(np.asarray, (u, r, w1, w2))
    c = np.cross(u, w1)
    use1 = np.sum(c * w2, 1) > 0
    n1 = np.where(use1[:, None], w1, w2)
    p = r - np.sum(r * u, 1, keepdims=True) * u
    p /= np.linalg.norm(p, axis=1, keepdims=True)
    q = np.cross(u, p)
    return np.arctan2(np.sum(n1 * q, 1), np.sum(n1 * p, 1))


@dataclass
class Layout:
    """面元高斯的固定索引（不随优化变化）。"""
    mi: np.ndarray
    mj: np.ndarray
    r: np.ndarray           # (m,3) 参考向量
    sm: np.ndarray          # (S,) 所属杆件
    sk: np.ndarray          # (S,) 轴向位置 (k−½)/K
    sleg: np.ndarray        # (S,) 肢号 0/1（圆柱基元为列号 0..3）
    sp: np.ndarray          # (S,) 横向位置 (p−½)/P
    sK: np.ndarray          # (S,) 该杆 K
    P: int
    kind: str = "angle"

    @property
    def n_surfels(self):
        return len(self.sm)

    @property
    def n_members(self):
        return len(self.mi)


def make_layout(nodes, mi, mj, spacing=0.22, P=2, kind="angle", center_xy=(0.0, 0.0), kmax=40):
    """按初始杆长确定每杆分段数 K_e=clip(ceil(L/spacing),2,kmax)。"""
    nodes = np.asarray(nodes, float)
    mi, mj = np.asarray(mi, np.int64), np.asarray(mj, np.int64)
    L0 = np.linalg.norm(nodes[mj] - nodes[mi], axis=1)
    K = np.clip(np.ceil(L0 / spacing).astype(int), 2, kmax)
    ncol = 4 if kind == "cylinder" else 2
    Pk = 1 if kind == "cylinder" else P
    sm, sk, sleg, sp, sK = [], [], [], [], []
    for e in range(len(mi)):
        k = (np.arange(K[e]) + 0.5) / K[e]
        for leg in range(ncol):
            for p in range(Pk):
                sm.append(np.full(K[e], e)); sk.append(k); sleg.append(np.full(K[e], leg))
                sp.append(np.full(K[e], (p + 0.5) / Pk)); sK.append(np.full(K[e], K[e]))
    cat = lambda x, dt=float: np.concatenate(x).astype(dt)
    return Layout(mi, mj, ref_vectors(nodes, mi, mj, center_xy), cat(sm, np.int64), cat(sk), cat(sleg, np.int64),
                  cat(sp), cat(sK), Pk, kind)


def generate(lay: Layout, V, b, phi, d1, d2, logit, Vend=None):
    """返回面元属性字典：mu, t1, t2, s1, s2, alpha（均为 autograd 可微数组）。

    Vend：独立端点消融时的 (m,2,3) 端点坐标（不共享节点）；None 时使用共享节点 V。
    """
    if Vend is None:
        vi, vj = V[lay.mi], V[lay.mj]
    else:
        vi, vj = Vend[:, 0, :], Vend[:, 1, :]
    u, n1, n2, L = frames(vi, vj, lay.r, phi)
    sm = lay.sm
    base = vi[sm] + lay.sk[:, None] * (vj - vi)[sm] + (d1[:, None] * n1 + d2[:, None] * n2)[sm]
    bs = b[sm]
    if lay.kind == "cylinder":
        # 4 列绕轴均布，面元法向沿径向，切向 (u, 切向)，半径 b/2，横向尺度 = 圆周四分之一弧长的一半
        ang = lay.sleg * (np.pi / 2)
        ca, sa = np.cos(ang)[:, None], np.sin(ang)[:, None]
        radial = ca * n1[sm] + sa * n2[sm]
        tang = -sa * n1[sm] + ca * n2[sm]
        cen = base + (0.5 * bs)[:, None] * (n1[sm] + n2[sm]) * 0.5 + (0.5 * bs)[:, None] * radial
        t2 = tang
        s2 = C_WIDTH * (np.pi / 4) * 0.5 * bs
    else:
        nleg = anp.where((lay.sleg == 0)[:, None], n1[sm], n2[sm])
        cen = base + (lay.sp * 1.0)[:, None] * bs[:, None] * nleg
        t2 = nleg
        s2 = C_WIDTH * bs / (2.0 * lay.P)
    t1 = u[sm]
    s1 = C_AXIAL * L[sm] / (2.0 * lay.sK)
    alpha = ALPHA0 * sigmoid(logit)[sm]
    return {"mu": cen, "t1": t1, "t2": t2, "s1": s1, "s2": s2, "alpha": alpha}


def generate_np(lay: Layout, V, b, phi, d1, d2, logit, Vend=None):
    """numpy 版（用于配对与可视化）。"""
    out = generate(lay, np.asarray(V, float), np.asarray(b, float), np.asarray(phi, float), np.asarray(d1, float),
                   np.asarray(d2, float), np.asarray(logit, float), None if Vend is None else np.asarray(Vend, float))
    return {k: np.asarray(v) for k, v in out.items()}


def legs_np(V, mi, mj, r, b, phi, d1, d2):
    """numpy：返回每杆两肢薄板（用于真值几何与出图）：heel_i, heel_j, n1, n2, u, L。"""
    V = np.asarray(V, float)
    vi, vj = V[mi], V[mj]
    u, n1, n2, L = (np.asarray(x) for x in frames(vi, vj, r, np.asarray(phi, float)))
    off = np.asarray(d1)[:, None] * n1 + np.asarray(d2)[:, None] * n2
    return vi + off, vj + off, n1, n2, u, L
