# -*- coding: utf-8 -*-
"""贝叶斯模型修正：TMCMC（过渡马尔可夫链蒙特卡洛）+ 模态降阶代理。

参数 θ = [u_1..u_G（各截面组在角钢目录中的连续档位坐标）, κ（斜/辅材连接刚度折减）, log10 k_v（基础刚度）]。
截面先验：规范逆向设计得到的离散分布 p_g(j) 展开为分段常数密度（档位 j 对应区间 [j−0.5, j+0.5)）；
无信息先验：类别允许范围内的均匀分布。似然：识别频率（相对误差 σ_f）+ 振型 MAC（σ_m），按 MAC 自动配对。
后验截面 = 每组档位样本四舍五入后的离散分布。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from towerkit import sections as S

from .design import MIN_SECTION
from .model import ORDER, interp_props


@dataclass
class PriorSpec:
    pmf: np.ndarray                  # (G, ncat) 截面先验离散分布
    kappa: tuple = (0.6, 1.05)       # 均匀先验
    logkv: tuple = (9.0, 11.5)

    def logpdf(self, th):
        G = self.pmf.shape[0]
        u = th[..., :G]
        j = np.rint(u).astype(int)
        ok = (j >= 0) & (j < self.pmf.shape[1])
        p = np.where(ok, self.pmf[np.arange(G), np.clip(j, 0, self.pmf.shape[1] - 1)], 0.0)
        lp = np.sum(np.log(np.maximum(p, 1e-300)), -1)
        k, v = th[..., G], th[..., G + 1]
        inside = (k >= self.kappa[0]) & (k <= self.kappa[1]) & (v >= self.logkv[0]) & (v <= self.logkv[1])
        return np.where(inside & np.all(p > 0, -1), lp, -np.inf)

    def sample(self, n, rng):
        G, nc = self.pmf.shape
        out = np.zeros((n, G + 2))
        for g in range(G):
            out[:, g] = rng.choice(nc, size=n, p=self.pmf[g]) + rng.uniform(-0.5, 0.5, n)
        out[:, G] = rng.uniform(*self.kappa, n)
        out[:, G + 1] = rng.uniform(*self.logkv, n)
        return out


class MixturePrior:
    """设计一致性混合先验：p(u) = Σ_s w_s Π_g q(round(u_g) − j_{s,g})，
    j_s 为第 s 个设计情景的逆向设计档位向量，q 为施工替代/选材偏差核（{0: p0, ±1, ±2}）。
    保留同一情景下各组截面的相关性（同一荷载水平使各组同升同降）。"""

    def __init__(self, designs_idx, kappa=(0.6, 1.05), logkv=(9.0, 11.5), ker=(0.70, 0.12, 0.03), weights=None,
                 ncat=None, floor=1e-4):
        self.floor = floor
        self.D = np.asarray(designs_idx, int)            # (S, G)
        self.S, self.G = self.D.shape
        self.w = np.full(self.S, 1.0 / self.S) if weights is None else np.asarray(weights) / np.sum(weights)
        k0, k1, k2 = ker
        self.q = {0: k0, 1: k1, -1: k1, 2: k2, -2: k2}
        self.kappa, self.logkv = kappa, logkv
        self.nc = ncat or len(ORDER)

    def _logq(self, d):
        out = np.full(d.shape, np.log(self.floor))       # 超出核支撑的偏差保留极小概率（容纳情景外设计）
        for k, v in self.q.items():
            out[d == k] = np.log(v)
        return out

    def logpdf(self, th):
        th = np.atleast_2d(th)
        j = np.rint(th[:, :self.G]).astype(int)
        d = j[:, None, :] - self.D[None, :, :]            # (n, S, G)
        lq = self._logq(d).sum(-1) + np.log(self.w)[None]
        m = lq.max(1)
        lp = np.where(np.isfinite(m), m + np.log(np.sum(np.exp(lq - m[:, None]), 1)), -np.inf)
        k, v = th[:, self.G], th[:, self.G + 1]
        inside = (k >= self.kappa[0]) & (k <= self.kappa[1]) & (v >= self.logkv[0]) & (v <= self.logkv[1]) \
            & np.all((j >= 0) & (j < self.nc), 1)
        return np.where(inside, lp, -np.inf)

    def sample(self, n, rng):
        s = rng.choice(self.S, size=n, p=self.w)
        keys = np.array(list(self.q)); pv = np.array([self.q[k] for k in keys]); pv /= pv.sum()
        off = rng.choice(keys, size=(n, self.G), p=pv)
        u = np.clip(self.D[s] + off, 0, self.nc - 1) + rng.uniform(-0.5, 0.5, (n, self.G))
        return np.column_stack([u, rng.uniform(*self.kappa, n), rng.uniform(*self.logkv, n)])

    def marginal_pmf(self):
        pmf = np.zeros((self.G, self.nc))
        for s in range(self.S):
            for k, v in self.q.items():
                j = np.clip(self.D[s] + k, 0, self.nc - 1)
                pmf[np.arange(self.G), j] += self.w[s] * v
        return pmf / pmf.sum(1, keepdims=True)


class ScalePrior:
    """常规模型修正（仅振动、无信息先验）：在统一截面基线上修正少数类别刚度/面积缩放系数 + κ + log k_v。
    θ = [s_1..s_C（对数缩放 ln s，均匀 [−ln4, ln4]）, κ, log k_v]。"""

    def __init__(self, n_scale, bound=np.log(4.0), kappa=(0.6, 1.05), logkv=(9.0, 11.5)):
        self.C, self.b, self.kappa, self.logkv = n_scale, bound, kappa, logkv
        self.G = n_scale

    def logpdf(self, th):
        th = np.atleast_2d(th)
        s = th[:, :self.C]
        ok = np.all(np.abs(s) <= self.b, 1) & (th[:, self.C] >= self.kappa[0]) & (th[:, self.C] <= self.kappa[1]) \
            & (th[:, self.C + 1] >= self.logkv[0]) & (th[:, self.C + 1] <= self.logkv[1])
        return np.where(ok, 0.0, -np.inf)

    def sample(self, n, rng):
        return np.column_stack([rng.uniform(-self.b, self.b, (n, self.C)), rng.uniform(*self.kappa, n),
                                rng.uniform(*self.logkv, n)])


def uniform_pmf(groups_cat, lo_steps=None, max_name="L250x35"):
    """无信息先验：每组在 [类别最小规格, max_name] 档位范围内均匀。"""
    nc = len(ORDER)
    pmf = np.zeros((len(groups_cat), nc))
    for g, cat in enumerate(groups_cat):
        amin = S.angle(MIN_SECTION[cat])
        hi = ORDER.index(max_name if cat == "main" else "L160x16")
        for j, nm in enumerate(ORDER):
            a = S.angle(nm)
            if a.A >= amin.A - 1e-12 and a.b >= amin.b - 1e-9 and j <= hi:
                pmf[g, j] = 1.0
    return pmf / pmf.sum(1, keepdims=True)


class ModalLikelihood:
    def __init__(self, rm, obs_modes, obs_free_idx, n_model=12, sigma_f=0.01, sigma_mac=0.05, w_mac=1.0,
                 to_props=None, mac_gate=0.6, f_gate=0.25):
        """obs_modes: [{'f','phi'}]；obs_free_idx: 观测通道对应的自由自由度索引（降阶模型 B 的行）。
        to_props: θ → (A, I, J) 每组特性的映射（缺省：θ[:G] 为档位坐标）。
        配对门限：MAC < mac_gate 或频率相对差 > f_gate 的观测模态记为“未配对”，按 MAC=mac_gate 罚分。"""
        self.rm = rm
        self.to_props = to_props
        self.mac_gate, self.f_gate = mac_gate, f_gate
        self.f_obs = np.array([m["f"] for m in obs_modes])
        self.phi_obs = np.array([m["phi"] for m in obs_modes]).T if obs_modes else np.zeros((len(obs_free_idx), 0))
        self.idx = np.asarray(obs_free_idx)
        self.n_model = n_model
        self.sf, self.sm, self.wm = sigma_f, sigma_mac, w_mac
        self.Bobs = rm.B[self.idx]

    def predict(self, th):
        if self.to_props is not None:
            (A, I, J), kap, lkv = self.to_props(th), th[-2], th[-1]
        else:
            G = len(self.rm.web)
            (A, I, J), kap, lkv = interp_props(th[:G]), th[G], th[G + 1]
        f, q = self.rm.eig(A, I, J, kap, lkv, n=self.n_model)
        return f, self.Bobs @ q

    def match(self, f, phs):
        num = np.abs(self.phi_obs.T @ phs) ** 2
        den = np.outer(np.sum(self.phi_obs ** 2, 0), np.sum(phs ** 2, 0)) + 1e-300
        M = num / den
        # 频率接近度 + MAC 联合配对（贪心、一一对应）
        score = M - 0.5 * np.abs(f[None, :] - self.f_obs[:, None]) / self.f_obs[:, None]
        used, pair = set(), []
        for i in np.argsort(-score.max(1)):
            order = np.argsort(-score[i])
            for j in order:
                if j not in used:
                    used.add(j); pair.append((i, j)); break
        pair.sort()
        return pair, M

    def loglik(self, th):
        if len(self.f_obs) == 0:          # 无有效识别模态：似然为常数，后验退化为先验
            return 0.0
        f, phs = self.predict(th)
        pair, M = self.match(f, phs)
        ll = 0.0
        for i, j in pair:
            rel = (f[j] - self.f_obs[i]) / self.f_obs[i]
            if M[i, j] < self.mac_gate or abs(rel) > self.f_gate:
                ll -= 0.5 * self.wm * ((1 - self.mac_gate) / self.sm) ** 2
                continue
            ll -= 0.5 * (rel / self.sf) ** 2
            ll -= 0.5 * self.wm * ((1 - M[i, j]) / self.sm) ** 2
        return ll


def tmcmc(loglik, prior: PriorSpec, n=600, rng=0, cov_scale=0.2, n_mh=3, max_stages=40, verbose=False):
    """Ching & Chen (2007) TMCMC。返回 (样本, log 似然, 阶段数, 证据 logZ)。"""
    rng = np.random.default_rng(rng)
    th = prior.sample(n, rng)
    ll = np.array([loglik(t) for t in th])
    beta, logZ, stage = 0.0, 0.0, 0
    while beta < 1.0 and stage < max_stages:
        stage += 1
        lo, hi = beta, 1.0
        for _ in range(60):          # 二分使权重 COV ≈ 1
            mid = 0.5 * (lo + hi)
            w = np.exp((mid - beta) * (ll - ll.max()))
            cov = w.std() / w.mean()
            if cov > 1.0:
                hi = mid
            else:
                lo = mid
        nb = min(1.0, hi if hi - beta > 1e-6 else 1.0)
        w = np.exp((nb - beta) * (ll - ll.max()))
        logZ += np.log(w.mean()) + (nb - beta) * ll.max()
        wn = w / w.sum()
        mu = wn @ th
        C = ((th - mu) * wn[:, None]).T @ (th - mu) * cov_scale ** 2 + 1e-8 * np.eye(th.shape[1])
        Lc = np.linalg.cholesky(C)
        idx = rng.choice(n, size=n, p=wn)
        th, ll = th[idx].copy(), ll[idx].copy()
        lp = prior.logpdf(th)
        acc = 0
        for _ in range(n_mh):
            prop = th + rng.normal(size=th.shape) @ Lc.T
            lpp = prior.logpdf(prop)
            llp = np.array([loglik(p) if np.isfinite(q) else -np.inf for p, q in zip(prop, lpp)])
            a = (lpp + nb * llp) - (lp + nb * ll)
            ok = np.log(rng.uniform(size=n)) < a
            th[ok], ll[ok], lp[ok] = prop[ok], llp[ok], lpp[ok]
            acc += ok.mean()
        beta = nb
        if verbose:
            print(f"stage {stage} beta={beta:.4f} acc={acc / n_mh:.2f}")
    return th, ll, stage, logZ


def posterior_sections(samples, G):
    """每组离散后验 pmf（ncat）、MAP 档位、90% 可信区间（档位）。"""
    nc = len(ORDER)
    j = np.clip(np.rint(samples[:, :G]).astype(int), 0, nc - 1)
    pmf = np.zeros((G, nc))
    for g in range(G):
        pmf[g] = np.bincount(j[:, g], minlength=nc) / len(j)
    mapj = pmf.argmax(1)
    lo = np.percentile(samples[:, :G], 5, axis=0)
    hi = np.percentile(samples[:, :G], 95, axis=0)
    return pmf, mapj, np.floor(lo + 0.5).astype(int), np.floor(hi + 0.5).astype(int)
