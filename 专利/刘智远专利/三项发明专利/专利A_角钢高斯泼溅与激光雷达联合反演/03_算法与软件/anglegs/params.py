# -*- coding: utf-8 -*-
"""桁架图参数化：节点坐标 V、杆件肢宽 b、肢朝向 phi、偏心 delta(2)、存在 logit；打包/解包与杆件局部标架。

约定（与 towerkit.lidar.build_geometry 一致）：杆件 e=(i,j)，轴向 u=(v_j-v_i)/L；参考向量 r_e
（塔身取指向塔心的水平向量，若与杆轴近平行则取竖直向量），n1=Rot_u(phi)·normalize(r_e-(r_e·u)u)，
n2=u×n1；角钢两肢分别张成 (u,n1)、(u,n2) 平面，肢背棱线 = 节点连线 + delta1·n1 + delta2·n2。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as onp

from . import _paths  # noqa: F401
import towerkit as tk
from towerkit import sections as S

B_MIN, B_MAX = 0.035, 0.26
#: GB/T 706 肢宽档（m）
B_TABLE = onp.array(sorted({a.b for a in S.ANGLES.values()}))


def ref_vectors(nodes, mi, mj, center_xy=None):
    """每杆的固定参考向量 r_e（由初始图计算后在优化中保持常量）。"""
    nodes = onp.asarray(nodes, float)
    mi, mj = onp.asarray(mi), onp.asarray(mj)
    c = onp.zeros(2) if center_xy is None else onp.asarray(center_xy, float)
    a, b = nodes[mi], nodes[mj]
    u = b - a
    u /= onp.linalg.norm(u, axis=1, keepdims=True)
    mid = 0.5 * (a + b)
    toc = onp.zeros_like(mid)
    toc[:, :2] = c - mid[:, :2]
    nt = onp.linalg.norm(toc, axis=1, keepdims=True)
    toc = onp.where(nt > 1e-6, toc / onp.maximum(nt, 1e-9), onp.array([1.0, 0, 0]))
    perp = toc - onp.sum(toc * u, 1, keepdims=True) * u
    bad = onp.linalg.norm(perp, axis=1) < 0.3
    r = toc.copy()
    r[bad] = onp.array([0, 0, 1.0])
    perp2 = r - onp.sum(r * u, 1, keepdims=True) * u
    bad2 = onp.linalg.norm(perp2, axis=1) < 0.3
    r[bad2] = onp.array([1.0, 0, 0])
    return r


def frames_np(vi, vj, r, phi):
    """numpy 版局部标架，返回 u, n1, n2, L。"""
    a = vj - vi
    L = onp.linalg.norm(a, axis=1)
    u = a / L[:, None]
    p = r - onp.sum(r * u, 1, keepdims=True) * u
    p /= onp.linalg.norm(p, axis=1, keepdims=True)
    q = onp.cross(u, p)
    n1 = onp.cos(phi)[:, None] * p + onp.sin(phi)[:, None] * q
    n2 = onp.cross(u, n1)
    return u, n1, n2, L


def phi_from_legs(u, r, w1):
    """由真值肢方向 w1 反求 phi（相对参考向量 r）。"""
    p = r - onp.sum(r * u, 1, keepdims=True) * u
    p /= onp.linalg.norm(p, axis=1, keepdims=True)
    q = onp.cross(u, p)
    return onp.arctan2(onp.sum(w1 * q, 1), onp.sum(w1 * p, 1))


@dataclass
class TrussParams:
    """待优化桁架参数（候选杆件池上的全量参数）。"""
    V: onp.ndarray                 # (n,3)
    b: onp.ndarray                 # (m,)
    phi: onp.ndarray               # (m,)
    delta: onp.ndarray             # (m,2)
    logit: onp.ndarray             # (m,)
    ext: onp.ndarray = field(default_factory=lambda: onp.zeros(7))   # 相机外参 t(3)、omega(3)、时间偏移 dt
    E: onp.ndarray | None = None   # 独立端点消融：(m,2,3)

    def copy(self):
        return TrussParams(self.V.copy(), self.b.copy(), self.phi.copy(), self.delta.copy(), self.logit.copy(),
                           self.ext.copy(), None if self.E is None else self.E.copy())

    @property
    def pi(self):
        return 1.0 / (1.0 + onp.exp(-self.logit))


BLOCKS = ("V", "b", "phi", "delta", "logit", "ext", "E")


class Packer:
    """按“自由块”把 TrussParams 打成一维向量；冻结块保持常量。"""

    def __init__(self, P: TrussParams, free: dict):
        self.P0 = P.copy()
        self.free = {k: v for k, v in free.items() if v is not None and getattr(P, k) is not None}
        self.slices = {}
        o = 0
        for k in BLOCKS:
            if k in self.free:
                idx = self.free[k]
                arr = getattr(P, k)
                n = arr[idx].size if idx is not True else arr.size
                self.slices[k] = (o, o + n)
                o += n
        self.n = o

    def _idx(self, k):
        return self.free[k]

    def pack(self, P: TrussParams):
        out = onp.zeros(self.n)
        for k, (a, b) in self.slices.items():
            arr = getattr(P, k)
            idx = self.free[k]
            out[a:b] = (arr if idx is True else arr[idx]).ravel()
        return out

    def unpack_np(self, x):
        P = self.P0.copy()
        for k, (a, b) in self.slices.items():
            arr = getattr(P, k)
            idx = self.free[k]
            if idx is True:
                setattr(P, k, onp.asarray(x[a:b]).reshape(arr.shape))
            else:
                arr = arr.copy()
                arr[idx] = onp.asarray(x[a:b]).reshape(arr[idx].shape)
                setattr(P, k, arr)
        return P

    def unpack_ad(self, x, anp):
        """autograd 版：返回 dict，冻结块为常量，自由块经 index 拼接保持可微。"""
        out = {}
        for k in BLOCKS:
            base = getattr(self.P0, k)
            if base is None:
                out[k] = None
                continue
            if k not in self.slices:
                out[k] = base
                continue
            a, b = self.slices[k]
            seg = x[a:b]
            idx = self.free[k]
            if idx is True:
                out[k] = anp.reshape(seg, base.shape)
            else:
                flat_base = base.reshape(base.shape[0], -1)
                rows = onp.asarray(idx)
                sel = onp.zeros(base.shape[0], int) - 1
                sel[rows] = onp.arange(len(rows))
                segm = anp.reshape(seg, (len(rows), flat_base.shape[1]))
                # 按行选择：自由行取 seg，冻结行取常量（用 one-hot 矩阵乘保持可微）
                Ssel = onp.zeros((base.shape[0], len(rows)))
                Ssel[rows, onp.arange(len(rows))] = 1.0
                mask = (sel >= 0).astype(float)[:, None]
                full = anp.dot(Ssel, segm) + flat_base * (1 - mask)
                out[k] = anp.reshape(full, base.shape)
        return out

    def bounds(self):
        bd = []
        for k in BLOCKS:
            if k not in self.slices:
                continue
            a, b = self.slices[k]
            if k == "b":
                bd += [(B_MIN, B_MAX)] * (b - a)
            elif k == "logit":
                bd += [(-7.0, 7.0)] * (b - a)
            elif k == "delta":
                bd += [(-0.08, 0.08)] * (b - a)
            else:
                bd += [(None, None)] * (b - a)
        return bd


def snap_width(b):
    """连续肢宽吸附到 GB/T 706 肢宽档。"""
    b = onp.asarray(b, float)
    return B_TABLE[onp.argmin(onp.abs(b[:, None] - B_TABLE[None]), axis=1)]


def spec_from_width(bw, length=None, cat=None):
    """由肢宽档取规格名：同肢宽下取该档中间肢厚（影像/激光不可观测肢厚，此为如实的约定，不做规范设计）。"""
    out = []
    for bb in onp.atleast_1d(bw):
        bmm = int(round(bb * 1000))
        names = [k for k, a in S.ANGLES.items() if int(round(a.b * 1000)) == bmm]
        names.sort(key=lambda k: S.ANGLES[k].t)
        out.append(names[len(names) // 2])
    return out
