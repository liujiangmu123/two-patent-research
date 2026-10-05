# -*- coding: utf-8 -*-
"""射线—面元高斯候选配对（numba 并行 DDA，均匀网格加速）。

对每条射线（相机像素射线或激光射线），沿射线遍历网格单元，收集横向距离不超过
“3 倍面元尺度 + 3 倍足迹半径 + 余量”的面元，按射线深度排序，最多保留前 maxk 个（遮挡后部贡献可忽略）。
配对只在外循环中按当前参数重建，内循环（可微损失）中固定。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit, prange


@njit(cache=True)
def _fill_grid(i0, i1, dims):
    ncell = dims[0] * dims[1] * dims[2]
    cnt = np.zeros(ncell + 1, np.int64)
    K = i0.shape[0]
    for k in range(K):
        for x in range(i0[k, 0], i1[k, 0] + 1):
            for y in range(i0[k, 1], i1[k, 1] + 1):
                for z in range(i0[k, 2], i1[k, 2] + 1):
                    cnt[x + dims[0] * (y + dims[1] * z) + 1] += 1
    for c in range(ncell):
        cnt[c + 1] += cnt[c]
    pos = cnt[:-1].copy()
    items = np.empty(cnt[-1], np.int64)
    for k in range(K):
        for x in range(i0[k, 0], i1[k, 0] + 1):
            for y in range(i0[k, 1], i1[k, 1] + 1):
                for z in range(i0[k, 2], i1[k, 2] + 1):
                    c = x + dims[0] * (y + dims[1] * z)
                    items[pos[c]] = k
                    pos[c] += 1
    return cnt, items


@njit(parallel=True, cache=True)
def _pairs(orig, dirs, tmax, sig0, sigk, mu, ax, ha, hw, gmin, cell, dims, cstart, citems, maxk, out_n, out_i,
           out_t):
    nr = orig.shape[0]
    gmax0 = gmin[0] + dims[0] * cell
    gmax1 = gmin[1] + dims[1] * cell
    gmax2 = gmin[2] + dims[2] * cell
    for r in prange(nr):
        o0, o1, o2 = orig[r, 0], orig[r, 1], orig[r, 2]
        d0, d1, d2 = dirs[r, 0], dirs[r, 1], dirs[r, 2]
        n = 0
        t0, t1 = 0.0, tmax[r]
        ok = True
        for kx in range(3):
            o = o0 if kx == 0 else (o1 if kx == 1 else o2)
            d = d0 if kx == 0 else (d1 if kx == 1 else d2)
            lo = gmin[kx]
            hi = gmax0 if kx == 0 else (gmax1 if kx == 1 else gmax2)
            if abs(d) < 1e-12:
                if o < lo or o > hi:
                    ok = False
            else:
                ta, tb = (lo - o) / d, (hi - o) / d
                if ta > tb:
                    ta, tb = tb, ta
                if ta > t0:
                    t0 = ta
                if tb < t1:
                    t1 = tb
        if not ok or t0 > t1:
            out_n[r] = 0
            continue
        te = t0 + 1e-7
        px, py, pz = o0 + d0 * te, o1 + d1 * te, o2 + d2 * te
        ix = min(max(int((px - gmin[0]) / cell), 0), dims[0] - 1)
        iy = min(max(int((py - gmin[1]) / cell), 0), dims[1] - 1)
        iz = min(max(int((pz - gmin[2]) / cell), 0), dims[2] - 1)
        sx = 1 if d0 > 0 else -1
        sy = 1 if d1 > 0 else -1
        sz = 1 if d2 > 0 else -1
        inf = 1e30
        tdx = abs(cell / d0) if abs(d0) > 1e-12 else inf
        tdy = abs(cell / d1) if abs(d1) > 1e-12 else inf
        tdz = abs(cell / d2) if abs(d2) > 1e-12 else inf
        nbx = gmin[0] + (ix + (1 if sx > 0 else 0)) * cell
        nby = gmin[1] + (iy + (1 if sy > 0 else 0)) * cell
        nbz = gmin[2] + (iz + (1 if sz > 0 else 0)) * cell
        tmx = (nbx - o0) / d0 if abs(d0) > 1e-12 else inf
        tmy = (nby - o1) / d1 if abs(d1) > 1e-12 else inf
        tmz = (nbz - o2) / d2 if abs(d2) > 1e-12 else inf
        while True:
            c = ix + dims[0] * (iy + dims[1] * iz)
            for q in range(cstart[c], cstart[c + 1]):
                s = citems[q]
                wx, wy, wz = mu[s, 0] - o0, mu[s, 1] - o1, mu[s, 2] - o2
                tc = wx * d0 + wy * d1 + wz * d2
                if tc <= 1e-3 or tc > tmax[r] + ha[s]:
                    continue
                # 射线（直线）与面元长轴线段（μ ± ha·ax）的最近距离
                bb = d0 * ax[s, 0] + d1 * ax[s, 1] + d2 * ax[s, 2]
                dd_ = -tc
                ee = -(wx * ax[s, 0] + wy * ax[s, 1] + wz * ax[s, 2])
                den = 1.0 - bb * bb
                if den > 1e-9:
                    sp = (ee - bb * dd_) / den
                else:
                    sp = 0.0
                if sp > ha[s]:
                    sp = ha[s]
                elif sp < -ha[s]:
                    sp = -ha[s]
                tt = sp * bb - dd_
                if tt <= 1e-3:
                    continue
                qx = -wx + tt * d0 - sp * ax[s, 0]
                qy = -wy + tt * d1 - sp * ax[s, 1]
                qz = -wz + tt * d2 - sp * ax[s, 2]
                lim = hw[s] + 3.0 * (sig0[r] + sigk[r] * tt)
                if qx * qx + qy * qy + qz * qz > lim * lim:
                    continue
                dup = False
                for j in range(n):
                    if out_i[r, j] == s:
                        dup = True
                        break
                if dup:
                    continue
                if n < maxk:
                    out_i[r, n] = s
                    out_t[r, n] = tc
                    n += 1
                else:
                    jm = 0
                    for j in range(1, maxk):
                        if out_t[r, j] > out_t[r, jm]:
                            jm = j
                    if tc < out_t[r, jm]:
                        out_i[r, jm] = s
                        out_t[r, jm] = tc
            tnext = min(tmx, min(tmy, tmz))
            if tnext > t1:
                break
            if tmx <= tmy and tmx <= tmz:
                ix += sx; tmx += tdx
                if ix < 0 or ix >= dims[0]:
                    break
            elif tmy <= tmz:
                iy += sy; tmy += tdy
                if iy < 0 or iy >= dims[1]:
                    break
            else:
                iz += sz; tmz += tdz
                if iz < 0 or iz >= dims[2]:
                    break
        # 插入排序（按深度升序）
        for a in range(1, n):
            ki, kt = out_i[r, a], out_t[r, a]
            b = a - 1
            while b >= 0 and out_t[r, b] > kt:
                out_i[r, b + 1] = out_i[r, b]
                out_t[r, b + 1] = out_t[r, b]
                b -= 1
            out_i[r, b + 1] = ki
            out_t[r, b + 1] = kt
        out_n[r] = n


@dataclass
class Pairs:
    """按射线、深度排序的配对表。"""
    pr: np.ndarray      # (Np,) 射线号
    ps: np.ndarray      # (Np,) 面元号
    tc: np.ndarray      # (Np,) 配对时刻的中心深度
    start: np.ndarray   # (Nr,) 每条射线的首配对位置
    end: np.ndarray     # (Nr,) 末配对位置（不含）
    n_rays: int
    overflow: int

    @property
    def n(self):
        return len(self.pr)

    def pair_start(self):
        """每个配对所在射线的首配对位置（用于射线内排他累积）。"""
        return self.start[self.pr]


def build_pairs(mu, ax, ha, hw, orig, dirs, tmax, sig0, sigk, cell=0.5, maxk=48) -> Pairs:
    """mu/ax：面元中心与长轴方向；ha：长轴半长（≈3·s1）；hw：横向容限（≈3·s2+余量）。"""
    mu = np.ascontiguousarray(mu, np.float64)
    ax = np.ascontiguousarray(ax, np.float64)
    ha = np.ascontiguousarray(ha, np.float64)
    hw = np.ascontiguousarray(hw, np.float64)
    rad = ha + hw + 3.0 * float(np.max(sigk)) * 60.0
    lo, hi = mu - rad[:, None], mu + rad[:, None]
    gmin = lo.min(axis=0) - 0.05
    gmax = hi.max(axis=0) + 0.05
    dims = np.maximum(np.ceil((gmax - gmin) / cell).astype(np.int64), 1)
    i0 = np.clip(((lo - gmin) / cell).astype(np.int64), 0, dims - 1)
    i1 = np.clip(((hi - gmin) / cell).astype(np.int64), 0, dims - 1)
    cstart, citems = _fill_grid(i0, i1, dims)
    nr = len(orig)
    out_n = np.zeros(nr, np.int64)
    out_i = np.full((nr, maxk), -1, np.int64)
    out_t = np.zeros((nr, maxk), np.float64)
    _pairs(np.ascontiguousarray(orig, np.float64), np.ascontiguousarray(dirs, np.float64),
           np.ascontiguousarray(tmax, np.float64), np.ascontiguousarray(sig0, np.float64),
           np.ascontiguousarray(sigk, np.float64), mu, ax, ha, hw, gmin, float(cell), dims, cstart, citems,
           int(maxk), out_n, out_i, out_t)
    mask = np.arange(maxk)[None, :] < out_n[:, None]
    pr = np.repeat(np.arange(nr), out_n)
    ps = out_i[mask]
    tc = out_t[mask]
    end = np.cumsum(out_n)
    start = end - out_n
    return Pairs(pr.astype(np.int64), ps.astype(np.int64), tc, start.astype(np.int64), end.astype(np.int64), nr,
                 int(np.sum(out_n >= maxk)))


def concat_pairs(a: Pairs, b: Pairs) -> Pairs:
    """把两组射线（如相机与激光）的配对拼接，射线号整体平移。"""
    off_r = a.n_rays
    off_p = a.n
    return Pairs(np.concatenate([a.pr, b.pr + off_r]), np.concatenate([a.ps, b.ps]), np.concatenate([a.tc, b.tc]),
                 np.concatenate([a.start, b.start + off_p]), np.concatenate([a.end, b.end + off_p]),
                 a.n_rays + b.n_rays, a.overflow + b.overflow)
