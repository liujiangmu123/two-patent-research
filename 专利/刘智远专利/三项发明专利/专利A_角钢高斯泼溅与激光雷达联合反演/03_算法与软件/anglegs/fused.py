# -*- coding: utf-8 -*-
"""融合算子（numba 并行，前向 + 解析反向）：射线—面元响应、相机合成损失、激光距离/自由空间损失。

数学定义与 render.py 中的 autograd 参考实现完全相同（tests 中做梯度一致性校验），
区别在于把逐配对的数十个中间数组融合到单个核函数中，避免 numpy 大数组的反复分配与 np.add.at 散射。
"""
from __future__ import annotations

import math

import numpy as np
from autograd.extend import defvjp_argnums, primitive
from numba import njit, prange

EPS_DET = 1e-18
NDMIN = 0.08
HUB = 0.05


# ====================================================================== 单配对响应（供假设检验核函数内联调用）
@njit(cache=True, inline="always")
def _resp_one(mux, muy, muz, t1x, t1y, t1z, t2x, t2y, t2z, S1, S2, A, ox, oy, oz, dx, dy, dz, E1x, E1y, E1z,
              E2x, E2y, E2z, sb0, sbk, lim, fp):
    wx = mux - ox; wy = muy - oy; wz = muz - oz
    tc = wx * dx + wy * dy + wz * dz
    rvx = wx - tc * dx; rvy = wy - tc * dy; rvz = wz - tc * dz
    r1 = rvx * E1x + rvy * E1y + rvz * E1z
    r2 = rvx * E2x + rvy * E2y + rvz * E2z
    a1 = t1x * E1x + t1y * E1y + t1z * E1z
    a2 = t1x * E2x + t1y * E2y + t1z * E2z
    b1 = t2x * E1x + t2y * E1y + t2z * E1z
    b2 = t2x * E2x + t2y * E2y + t2z * E2z
    q1 = S1 * S1; q2 = S2 * S2
    c11 = q1 * a1 * a1 + q2 * b1 * b1
    c12 = q1 * a1 * a2 + q2 * b1 * b2
    c22 = q1 * a2 * a2 + q2 * b2 * b2
    dS = c11 * c22 - c12 * c12
    if dS < 0.0:
        dS = 0.0
    sb = (sb0 + sbk * tc) if fp else 1e-4
    sb2 = sb * sb
    m11 = c11 + sb2; m22 = c22 + sb2
    dM = m11 * m22 - c12 * c12
    Q = (m22 * r1 * r1 - 2.0 * c12 * r1 * r2 + m11 * r2 * r2) / dM
    h = A * math.sqrt((dS + EPS_DET) / dM) * math.exp(-0.5 * Q)
    nx = t1y * t2z - t1z * t2y
    ny = t1z * t2x - t1x * t2z
    nz = t1x * t2y - t1y * t2x
    nd = nx * dx + ny * dy + nz * dz
    nr = nx * rvx + ny * rvy + nz * rvz
    nds = nd
    if abs(nd) < NDMIN:
        nds = NDMIN if nd >= 0 else -NDMIN
    c = nr / nds
    if c > lim:
        c = lim
    elif c < -lim:
        c = -lim
    return h, tc + c, nx, ny, nz


@njit(parallel=True, cache=True)
def hyp_eval(term, nh, rays_n, bst, ben, bps, btc, excl_lo, excl_hi, hst, hen, hps, htc, cnt,
             mu, t1, t2, s1, s2, al, alb, hmu, ht1, ht2, hs1, hs2, hal, halb,
             o, d, e1, e2, sb0, sbk, fp, sun, a0, a1c,
             mask, gray, sky, valid, wp, dmeas, sigr, wret, wfree, eps, ground, pdet, out):
    """对 nh 个假设 × rays_n 条射线并行计算逐射线损失（两路已按深度排序的配对在线归并合成）。

    基准配对（其他杆件）：射线 r 的 [bst[r], ben[r])，剔除面元号 ∈ [excl_lo, excl_hi)；
    假设配对：射线 r 的 [hst[r], hen[r])，局部面元号 hps // cnt 为假设号。
    term：0 相机（轮廓 BCE + 灰度 Huber），1 激光有回波（混合似然 + 前方自由空间），2 自由空间射线。
    """
    for q in prange(nh * rays_n):
        hh = q // rays_n
        r = q % rays_n
        ox, oy, oz = o[r, 0], o[r, 1], o[r, 2]
        dx, dy, dz = d[r, 0], d[r, 1], d[r, 2]
        E1x, E1y, E1z = e1[r, 0], e1[r, 1], e1[r, 2]
        E2x, E2y, E2z = e2[r, 0], e2[r, 1], e2[r, 2]
        i = bst[r]; j = hst[r]
        T = 1.0; logT = 0.0; acc = 0.0; lik = 0.0; fr = 0.0
        while True:
            # 跳过被剔除的基准配对与其他假设的配对
            while i < ben[r] and bps[i] >= excl_lo and bps[i] < excl_hi:
                i += 1
            while j < hen[r] and hps[j] // cnt != hh:
                j += 1
            ib = i < ben[r]
            jh = j < hen[r]
            if not ib and not jh:
                break
            use_b = ib and ((not jh) or btc[i] <= htc[j])
            if use_b:
                s = bps[i]
                hk, tk, nx, ny, nz = _resp_one(mu[s, 0], mu[s, 1], mu[s, 2], t1[s, 0], t1[s, 1], t1[s, 2],
                                               t2[s, 0], t2[s, 1], t2[s, 2], s1[s], s2[s], al[s], ox, oy, oz,
                                               dx, dy, dz, E1x, E1y, E1z, E2x, E2y, E2z, sb0[r], sbk[r],
                                               3.0 * max(s1[s], s2[s]), fp)
                tcp = btc[i]
                cal = alb[s]
                i += 1
            else:
                s = hps[j]
                hk, tk, nx, ny, nz = _resp_one(hmu[s, 0], hmu[s, 1], hmu[s, 2], ht1[s, 0], ht1[s, 1], ht1[s, 2],
                                               ht2[s, 0], ht2[s, 1], ht2[s, 2], hs1[s], hs2[s], hal[s], ox, oy, oz,
                                               dx, dy, dz, E1x, E1y, E1z, E2x, E2y, E2z, sb0[r], sbk[r],
                                               3.0 * max(hs1[s], hs2[s]), fp)
                tcp = htc[j]
                cal = halb
                j += 1
            if term == 0:
                nd = nx * dx + ny * dy + nz * dz
                sg = -1.0 if nd > 0 else 1.0
                lam = sg * (nx * sun[0] + ny * sun[1] + nz * sun[2])
                if lam < 0.0:
                    lam = 0.0
                acc += hk * T * cal * (a0 + a1c * lam)
            elif term == 1:
                z = (dmeas[r] - tk) / sigr
                lik += hk * T * math.exp(-0.5 * z * z)
                if tcp < dmeas[r] - 3.0 * sigr - 0.05:
                    fr -= math.log1p(-hk)
            else:
                fr -= math.log1p(-hk)
            T *= (1.0 - hk)
            logT += math.log1p(-hk)
        if term == 0:
            O = -math.expm1(logT)
            bce = -(mask[r] * math.log(O + 1e-6) + (1.0 - mask[r]) * logT)
            e = acc + T * sky[r] - gray[r]
            hub = 0.5 * e * e / HUB if abs(e) < HUB else abs(e) - 0.5 * HUB
            out[hh, r] = valid[r] * (bce + wp * hub / HUB)
        elif term == 1:
            out[hh, r] = -wret * math.log(eps + lik) + wfree * fr
        else:
            if ground[r] > 0:
                out[hh, r] = wfree * fr
            else:
                out[hh, r] = -wfree * math.log((1.0 - pdet) + pdet * math.exp(-fr))


# ====================================================================== 响应
@njit(parallel=True, cache=True)
def _resp_fwd(pr, ps, mu, t1, t2, s1, s2, al, o, d, e1, e2, sig0, sigk, lim, blur, fp, h, tk):
    n = pr.shape[0]
    for p in prange(n):
        r = pr[p]; s = ps[p]
        wx = mu[s, 0] - o[r, 0]; wy = mu[s, 1] - o[r, 1]; wz = mu[s, 2] - o[r, 2]
        dx = d[r, 0]; dy = d[r, 1]; dz = d[r, 2]
        tc = wx * dx + wy * dy + wz * dz
        rvx = wx - tc * dx; rvy = wy - tc * dy; rvz = wz - tc * dz
        r1 = rvx * e1[r, 0] + rvy * e1[r, 1] + rvz * e1[r, 2]
        r2 = rvx * e2[r, 0] + rvy * e2[r, 1] + rvz * e2[r, 2]
        a1 = t1[s, 0] * e1[r, 0] + t1[s, 1] * e1[r, 1] + t1[s, 2] * e1[r, 2]
        a2 = t1[s, 0] * e2[r, 0] + t1[s, 1] * e2[r, 1] + t1[s, 2] * e2[r, 2]
        b1 = t2[s, 0] * e1[r, 0] + t2[s, 1] * e1[r, 1] + t2[s, 2] * e1[r, 2]
        b2 = t2[s, 0] * e2[r, 0] + t2[s, 1] * e2[r, 1] + t2[s, 2] * e2[r, 2]
        q1 = s1[s] * s1[s]; q2 = s2[s] * s2[s]
        c11 = q1 * a1 * a1 + q2 * b1 * b1
        c12 = q1 * a1 * a2 + q2 * b1 * b2
        c22 = q1 * a2 * a2 + q2 * b2 * b2
        dS = c11 * c22 - c12 * c12
        if dS < 0.0:
            dS = 0.0
        if fp:
            sb = sig0[r] + sigk[r] * tc + blur
        else:
            sb = 1e-4 + blur
        sb2 = sb * sb
        m11 = c11 + sb2; m22 = c22 + sb2
        dM = m11 * m22 - c12 * c12
        Q = (m22 * r1 * r1 - 2.0 * c12 * r1 * r2 + m11 * r2 * r2) / dM
        h[p] = al[s] * math.sqrt((dS + EPS_DET) / dM) * math.exp(-0.5 * Q)
        nx = t1[s, 1] * t2[s, 2] - t1[s, 2] * t2[s, 1]
        ny = t1[s, 2] * t2[s, 0] - t1[s, 0] * t2[s, 2]
        nz = t1[s, 0] * t2[s, 1] - t1[s, 1] * t2[s, 0]
        nd = nx * dx + ny * dy + nz * dz
        nr = nx * rvx + ny * rvy + nz * rvz
        nds = nd
        if abs(nd) < NDMIN:
            nds = NDMIN if nd >= 0 else -NDMIN
        c = nr / nds
        if c > lim[p]:
            c = lim[p]
        elif c < -lim[p]:
            c = -lim[p]
        tk[p] = tc + c


@njit(parallel=True, cache=True)
def _resp_bwd(chunks, start, end, ps, mu, t1, t2, s1, s2, al, o, d, e1, e2, sig0, sigk, lim, blur, fp, gh, gt,
              buf, go, gd, need_od):
    nch = chunks.shape[0] - 1
    for c in prange(nch):
        for r in range(chunks[c], chunks[c + 1]):
            dx = d[r, 0]; dy = d[r, 1]; dz = d[r, 2]
            E1x = e1[r, 0]; E1y = e1[r, 1]; E1z = e1[r, 2]
            E2x = e2[r, 0]; E2y = e2[r, 1]; E2z = e2[r, 2]
            gox = 0.0; goy = 0.0; goz = 0.0; gdx = 0.0; gdy = 0.0; gdz = 0.0
            for p in range(start[r], end[r]):
                ghp = gh[p]; gtp = gt[p]
                if ghp == 0.0 and gtp == 0.0:
                    continue
                s = ps[p]
                wx = mu[s, 0] - o[r, 0]; wy = mu[s, 1] - o[r, 1]; wz = mu[s, 2] - o[r, 2]
                tc = wx * dx + wy * dy + wz * dz
                rvx = wx - tc * dx; rvy = wy - tc * dy; rvz = wz - tc * dz
                r1 = rvx * E1x + rvy * E1y + rvz * E1z
                r2 = rvx * E2x + rvy * E2y + rvz * E2z
                T1x = t1[s, 0]; T1y = t1[s, 1]; T1z = t1[s, 2]
                T2x = t2[s, 0]; T2y = t2[s, 1]; T2z = t2[s, 2]
                a1 = T1x * E1x + T1y * E1y + T1z * E1z
                a2 = T1x * E2x + T1y * E2y + T1z * E2z
                b1 = T2x * E1x + T2y * E1y + T2z * E1z
                b2 = T2x * E2x + T2y * E2y + T2z * E2z
                S1 = s1[s]; S2 = s2[s]
                q1 = S1 * S1; q2 = S2 * S2
                c11 = q1 * a1 * a1 + q2 * b1 * b1
                c12 = q1 * a1 * a2 + q2 * b1 * b2
                c22 = q1 * a2 * a2 + q2 * b2 * b2
                dS = c11 * c22 - c12 * c12
                pos = dS > 0.0
                if not pos:
                    dS = 0.0
                if fp:
                    sb = sig0[r] + sigk[r] * tc + blur
                else:
                    sb = 1e-4 + blur
                sb2 = sb * sb
                m11 = c11 + sb2; m22 = c22 + sb2
                dM = m11 * m22 - c12 * c12
                inv = 1.0 / dM
                Q = (m22 * r1 * r1 - 2.0 * c12 * r1 * r2 + m11 * r2 * r2) * inv
                G = math.exp(-0.5 * Q)
                R = math.sqrt((dS + EPS_DET) * inv)
                A = al[s]
                # ---- h 路径
                gal = ghp * R * G
                gR = ghp * A * G
                gG = ghp * A * R
                gQ = -0.5 * G * gG
                dRdM = -0.5 * R * inv
                dRdS = 0.5 * R / (dS + EPS_DET) if pos else 0.0
                g_m11 = gQ * (r2 * r2 - Q * m22) * inv + gR * dRdM * m22
                g_m22 = gQ * (r1 * r1 - Q * m11) * inv + gR * dRdM * m11
                g_m12 = gQ * (-2.0 * r1 * r2 + 2.0 * Q * c12) * inv + gR * dRdM * (-2.0 * c12)
                g_dS = gR * dRdS
                g_r1 = gQ * (2.0 * m22 * r1 - 2.0 * c12 * r2) * inv
                g_r2 = gQ * (2.0 * m11 * r2 - 2.0 * c12 * r1) * inv
                g_c11 = g_m11 + g_dS * c22
                g_c22 = g_m22 + g_dS * c11
                g_c12 = g_m12 - 2.0 * g_dS * c12
                g_tc = 0.0
                if fp:
                    g_tc += (g_m11 + g_m22) * 2.0 * sb * sigk[r]
                g_q1 = g_c11 * a1 * a1 + g_c12 * a1 * a2 + g_c22 * a2 * a2
                g_q2 = g_c11 * b1 * b1 + g_c12 * b1 * b2 + g_c22 * b2 * b2
                g_a1 = 2.0 * g_c11 * q1 * a1 + g_c12 * q1 * a2
                g_a2 = g_c12 * q1 * a1 + 2.0 * g_c22 * q1 * a2
                g_b1 = 2.0 * g_c11 * q2 * b1 + g_c12 * q2 * b2
                g_b2 = g_c12 * q2 * b1 + 2.0 * g_c22 * q2 * b2
                gt1x = g_a1 * E1x + g_a2 * E2x; gt1y = g_a1 * E1y + g_a2 * E2y; gt1z = g_a1 * E1z + g_a2 * E2z
                gt2x = g_b1 * E1x + g_b2 * E2x; gt2y = g_b1 * E1y + g_b2 * E2y; gt2z = g_b1 * E1z + g_b2 * E2z
                grvx = g_r1 * E1x + g_r2 * E2x; grvy = g_r1 * E1y + g_r2 * E2y; grvz = g_r1 * E1z + g_r2 * E2z
                gdx_p = 0.0; gdy_p = 0.0; gdz_p = 0.0
                # ---- 深度路径
                g_tc += gtp
                nx = T1y * T2z - T1z * T2y
                ny = T1z * T2x - T1x * T2z
                nz = T1x * T2y - T1y * T2x
                nd = nx * dx + ny * dy + nz * dz
                nr = nx * rvx + ny * rvy + nz * rvz
                small = abs(nd) < NDMIN
                nds = nd
                if small:
                    nds = NDMIN if nd >= 0 else -NDMIN
                cc = nr / nds
                if gtp != 0.0 and abs(cc) < lim[p]:
                    g_nr = gtp / nds
                    g_nd = 0.0 if small else -gtp * nr / (nds * nds)
                    gnx = g_nr * rvx + g_nd * dx; gny = g_nr * rvy + g_nd * dy; gnz = g_nr * rvz + g_nd * dz
                    grvx += g_nr * nx; grvy += g_nr * ny; grvz += g_nr * nz
                    # n = t1 × t2：g_t1 += t2 × g_n，g_t2 += g_n × t1
                    gt1x += T2y * gnz - T2z * gny; gt1y += T2z * gnx - T2x * gnz; gt1z += T2x * gny - T2y * gnx
                    gt2x += gny * T1z - gnz * T1y; gt2y += gnz * T1x - gnx * T1z; gt2z += gnx * T1y - gny * T1x
                    gdx_p += g_nd * nx; gdy_p += g_nd * ny; gdz_p += g_nd * nz
                # ---- rv = w − tc·d，tc = w·d
                g_tc += -(grvx * dx + grvy * dy + grvz * dz)
                gwx = grvx + g_tc * dx; gwy = grvy + g_tc * dy; gwz = grvz + g_tc * dz
                gdx_p += -tc * grvx + g_tc * wx; gdy_p += -tc * grvy + g_tc * wy; gdz_p += -tc * grvz + g_tc * wz
                b = buf[c, s]
                b[0] += gwx; b[1] += gwy; b[2] += gwz
                b[3] += gt1x; b[4] += gt1y; b[5] += gt1z
                b[6] += gt2x; b[7] += gt2y; b[8] += gt2z
                b[9] += 2.0 * S1 * g_q1; b[10] += 2.0 * S2 * g_q2; b[11] += gal
                gox -= gwx; goy -= gwy; goz -= gwz
                gdx += gdx_p; gdy += gdy_p; gdz += gdz_p
            if need_od:
                go[r, 0] += gox; go[r, 1] += goy; go[r, 2] += goz
                gd[r, 0] += gdx; gd[r, 1] += gdy; gd[r, 2] += gdz


def _chunks(nr, nch=32):
    return np.linspace(0, nr, min(nch, max(1, nr)) + 1).astype(np.int64)


class RayConst:
    """一组射线的常量（配对、横截面基、足迹、限幅）。"""

    def __init__(self, pairs, e1, e2, sig0, sigk, lim, blur=0.0, footprint=True):
        self.pr, self.ps = pairs.pr, pairs.ps
        self.start, self.end = pairs.start, pairs.end
        self.pstart = pairs.start[pairs.pr]
        self.nr = pairs.n_rays
        self.e1, self.e2 = np.ascontiguousarray(e1), np.ascontiguousarray(e2)
        self.sig0, self.sigk = np.ascontiguousarray(sig0, float), np.ascontiguousarray(sigk, float)
        self.lim = np.ascontiguousarray(lim, float)
        self.blur, self.fp = float(blur), bool(footprint)
        self.chunks = _chunks(self.nr)


@primitive
def response(mu, t1, t2, s1, s2, al, o, d, C: RayConst):
    """返回 (2, Np)：第 0 行 h，第 1 行 t_s。"""
    n = len(C.pr)
    h = np.empty(n); tk = np.empty(n)
    _resp_fwd(C.pr, C.ps, np.ascontiguousarray(mu), np.ascontiguousarray(t1), np.ascontiguousarray(t2),
              np.ascontiguousarray(s1), np.ascontiguousarray(s2), np.ascontiguousarray(al), np.ascontiguousarray(o),
              np.ascontiguousarray(d), C.e1, C.e2, C.sig0, C.sigk, C.lim, C.blur, C.fp, h, tk)
    return np.stack([h, tk])


def _response_vjp(argnums, ans, args, kwargs):
    mu, t1, t2, s1, s2, al, o, d, C = args
    need_od = (6 in argnums) or (7 in argnums)

    def vjp(g):
        g = np.asarray(g)
        S = mu.shape[0]
        buf = np.zeros((len(C.chunks) - 1, S, 12))
        go = np.zeros(o.shape if need_od else (1, 3))
        gd = np.zeros(d.shape if need_od else (1, 3))
        _resp_bwd(C.chunks, C.start, C.end, C.ps, np.ascontiguousarray(mu), np.ascontiguousarray(t1),
                  np.ascontiguousarray(t2), np.ascontiguousarray(s1), np.ascontiguousarray(s2),
                  np.ascontiguousarray(al), np.ascontiguousarray(o), np.ascontiguousarray(d), C.e1, C.e2, C.sig0,
                  C.sigk, C.lim, C.blur, C.fp, np.ascontiguousarray(g[0]), np.ascontiguousarray(g[1]), buf, go, gd,
                  need_od)
        Gs = buf.sum(0)
        parts = {0: Gs[:, 0:3], 1: Gs[:, 3:6], 2: Gs[:, 6:9], 3: Gs[:, 9], 4: Gs[:, 10], 5: Gs[:, 11],
                 6: go, 7: gd}
        return tuple(parts[a] for a in argnums)
    return vjp


defvjp_argnums(response, _response_vjp)


# ====================================================================== 相机合成损失（逐配对颜色 cpair：反照率 × 由面元法向与太阳方向计算的明暗）
@njit(parallel=True, cache=True)
def _cam_fwd(start, end, h, cpair, mask, gray, sky, valid, wp, out):
    nr = start.shape[0]
    for r in prange(nr):
        T = 1.0; logT = 0.0; acc = 0.0
        for p in range(start[r], end[r]):
            hk = h[p]
            acc += hk * T * cpair[p]
            T *= (1.0 - hk)
            logT += math.log1p(-hk)
        O = -math.expm1(logT)
        bce = -(mask[r] * math.log(O + 1e-6) + (1.0 - mask[r]) * logT)
        e = acc + T * sky[r] - gray[r]
        hub = 0.5 * e * e / HUB if abs(e) < HUB else abs(e) - 0.5 * HUB
        out[r] = valid[r] * (bce + wp * hub / HUB)


@njit(parallel=True, cache=True)
def _cam_bwd(start, end, h, cpair, mask, gray, sky, valid, wp, g, gh, gc):
    nr = start.shape[0]
    for r in prange(nr):
        gr = g[r] * valid[r]
        if gr == 0.0 or end[r] == start[r]:
            continue
        T = 1.0; logT = 0.0; acc = 0.0
        for p in range(start[r], end[r]):
            hk = h[p]
            acc += hk * T * cpair[p]
            T *= (1.0 - hk)
            logT += math.log1p(-hk)
        Tend = math.exp(logT)
        O = -math.expm1(logT)
        dbce_dlogT = mask[r] * Tend / (O + 1e-6) - (1.0 - mask[r])
        e = acc + Tend * sky[r] - gray[r]
        dhub = e / HUB if abs(e) < HUB else (1.0 if e > 0 else -1.0)
        kg = wp * dhub / HUB
        Tafter = Tend
        suffix = Tend * sky[r]
        for p in range(end[r] - 1, start[r] - 1, -1):
            hk = h[p]
            om = 1.0 - hk
            Tbefore = Tafter / om
            ck = cpair[p]
            wk = hk * Tbefore
            dgray = Tbefore * ck - suffix / om
            gh[p] = gr * (dbce_dlogT * (-1.0 / om) + kg * dgray)
            gc[p] = gr * kg * wk
            suffix += wk * ck
            Tafter = Tbefore


class CamConst:
    def __init__(self, rc: RayConst, mask, gray, sky, valid, w_photo):
        self.rc = rc
        self.mask, self.gray, self.sky = (np.ascontiguousarray(a, float) for a in (mask, gray, sky))
        self.valid = np.ascontiguousarray(valid, float)
        self.wp = float(w_photo)


@primitive
def cam_loss(H, cpair, K: CamConst):
    rc = K.rc
    out = np.empty(rc.nr)
    _cam_fwd(rc.start, rc.end, np.ascontiguousarray(H[0]), np.ascontiguousarray(cpair), K.mask, K.gray, K.sky,
             K.valid, K.wp, out)
    return out


def _cam_vjp(argnums, ans, args, kwargs):
    H, cpair, K = args

    def vjp(g):
        rc = K.rc
        gh = np.zeros(H.shape[1]); gc = np.zeros(H.shape[1])
        _cam_bwd(rc.start, rc.end, np.ascontiguousarray(H[0]), np.ascontiguousarray(cpair), K.mask, K.gray, K.sky,
                 K.valid, K.wp, np.ascontiguousarray(g, float), gh, gc)
        parts = {0: np.stack([gh, np.zeros_like(gh)]), 1: gc}
        return tuple(parts[a] for a in argnums)
    return vjp


defvjp_argnums(cam_loss, _cam_vjp)


# ====================================================================== 激光有回波射线
@njit(parallel=True, cache=True)
def _ret_fwd(start, end, h, tk, dmeas, sigr, front, wret, wfree, eps, out):
    nr = start.shape[0]
    for r in prange(nr):
        T = 1.0; lik = 0.0; fr = 0.0
        for p in range(start[r], end[r]):
            hk = h[p]
            z = (dmeas[r] - tk[p]) / sigr
            lik += hk * T * math.exp(-0.5 * z * z)
            T *= (1.0 - hk)
            if front[p] > 0:
                fr -= math.log1p(-hk)
        out[r] = -wret * math.log(eps + lik) + wfree * fr


@njit(parallel=True, cache=True)
def _ret_bwd(start, end, h, tk, dmeas, sigr, front, wret, wfree, eps, g, gh, gt):
    nr = start.shape[0]
    for r in prange(nr):
        gr = g[r]
        if gr == 0.0 or end[r] == start[r]:
            continue
        T = 1.0; lik = 0.0
        for p in range(start[r], end[r]):
            hk = h[p]
            z = (dmeas[r] - tk[p]) / sigr
            lik += hk * T * math.exp(-0.5 * z * z)
            T *= (1.0 - hk)
        k = -wret / (eps + lik)
        Tafter = T
        B = 0.0
        for p in range(end[r] - 1, start[r] - 1, -1):
            hk = h[p]
            om = 1.0 - hk
            Tbefore = Tafter / om
            z = (dmeas[r] - tk[p]) / sigr
            ph = math.exp(-0.5 * z * z)
            wk = hk * Tbefore
            dlik_dh = Tbefore * ph - B / om
            gh[p] = gr * (k * dlik_dh + (wfree / om if front[p] > 0 else 0.0))
            gt[p] = gr * k * wk * ph * z / sigr
            B += wk * ph
            Tafter = Tbefore


class RetConst:
    def __init__(self, rc: RayConst, dmeas, sigr, front, wret, wfree, eps=2e-3):
        self.rc = rc
        self.dmeas = np.ascontiguousarray(dmeas, float)
        self.sigr = float(sigr)
        self.front = np.ascontiguousarray(front, float)
        self.wret, self.wfree, self.eps = float(wret), float(wfree), float(eps)


@primitive
def ret_loss(H, K: RetConst):
    rc = K.rc
    out = np.empty(rc.nr)
    _ret_fwd(rc.start, rc.end, np.ascontiguousarray(H[0]), np.ascontiguousarray(H[1]), K.dmeas, K.sigr, K.front,
             K.wret, K.wfree, K.eps, out)
    return out


def _ret_vjp(ans, H, K):
    def vjp(g):
        rc = K.rc
        gh = np.zeros(H.shape[1]); gt = np.zeros(H.shape[1])
        _ret_bwd(rc.start, rc.end, np.ascontiguousarray(H[0]), np.ascontiguousarray(H[1]), K.dmeas, K.sigr, K.front,
                 K.wret, K.wfree, K.eps, np.ascontiguousarray(g, float), gh, gt)
        return np.stack([gh, gt])
    return vjp


from autograd.extend import defvjp  # noqa: E402

defvjp(ret_loss, _ret_vjp, None)


# ====================================================================== 自由空间射线（地面回波 / 无回波）
@njit(parallel=True, cache=True)
def _free_fwd(start, end, h, ground, wfree, pdet, out):
    nr = start.shape[0]
    for r in prange(nr):
        fs = 0.0
        for p in range(start[r], end[r]):
            fs -= math.log1p(-h[p])
        if ground[r] > 0:
            out[r] = wfree * fs
        else:
            T = math.exp(-fs)
            out[r] = -wfree * math.log((1.0 - pdet) + pdet * T)


@njit(parallel=True, cache=True)
def _free_bwd(start, end, h, ground, wfree, pdet, g, gh):
    nr = start.shape[0]
    for r in prange(nr):
        gr = g[r]
        if gr == 0.0 or end[r] == start[r]:
            continue
        fs = 0.0
        for p in range(start[r], end[r]):
            fs -= math.log1p(-h[p])
        if ground[r] > 0:
            k = wfree
        else:
            T = math.exp(-fs)
            k = wfree * pdet * T / ((1.0 - pdet) + pdet * T)
        for p in range(start[r], end[r]):
            gh[p] = gr * k / (1.0 - h[p])


class FreeConst:
    def __init__(self, rc: RayConst, ground, wfree, pdet):
        self.rc = rc
        self.ground = np.ascontiguousarray(ground, float)
        self.wfree, self.pdet = float(wfree), float(pdet)


@primitive
def free_loss(H, K: FreeConst):
    rc = K.rc
    out = np.empty(rc.nr)
    _free_fwd(rc.start, rc.end, np.ascontiguousarray(H[0]), K.ground, K.wfree, K.pdet, out)
    return out


def _free_vjp(ans, H, K):
    def vjp(g):
        rc = K.rc
        gh = np.zeros(H.shape[1])
        _free_bwd(rc.start, rc.end, np.ascontiguousarray(H[0]), K.ground, K.wfree, K.pdet,
                  np.ascontiguousarray(g, float), gh)
        return np.stack([gh, np.zeros_like(gh)])
    return vjp


defvjp(free_loss, _free_vjp, None)
