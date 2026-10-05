# -*- coding: utf-8 -*-
"""anglegs 单元测试：生成函数、配对、响应闭式解、融合算子梯度、拓扑零能模态、评价指标、命令行。"""
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from anglegs import fused as FU  # noqa: E402
from anglegs import metrics as ME  # noqa: E402
from anglegs import topology as TP  # noqa: E402
from anglegs.optimize import CamData, Config, LidData, Problem  # noqa: E402
from anglegs.raycast import build_pairs  # noqa: E402
from anglegs.render import ray_basis  # noqa: E402
from anglegs.surfels import C_WIDTH, frames, generate_np, make_layout, phi_from_legs  # noqa: E402


def _tiny():
    """三角形桁架片 + 一根交叉杆（6 节点 7 杆）。"""
    V = np.array([[0, 0, 0], [2, 0, 0], [2, 0, 2], [0, 0, 2], [1, 0.0, 4.0], [1, 0.0, 1.0]], float)
    mi = np.array([0, 1, 2, 3, 0, 2, 3])
    mj = np.array([1, 2, 3, 0, 2, 4, 4])
    return V, mi, mj


def test_generator_frames_and_shared_nodes():
    V, mi, mj = _tiny()
    lay = make_layout(V, mi, mj, spacing=0.3)
    m = len(mi)
    b = np.full(m, 0.08); phi = np.zeros(m); d = np.zeros(m); lg = np.full(m, 3.0)
    S = generate_np(lay, V, b, phi, d, d, lg)
    u, n1, n2, L = (np.asarray(a) for a in frames(V[mi], V[mj], lay.r, phi))
    assert np.allclose(np.sum(u * n1, 1), 0, atol=1e-12)
    assert np.allclose(np.cross(u, n1), n2, atol=1e-12)
    # 移动节点 2：与之相连的杆件面元全部移动，其余不动
    V2 = V.copy(); V2[2] += [0, 0.05, 0]
    S2 = generate_np(lay, V2, b, phi, d, d, lg)
    moved = np.linalg.norm(S2["mu"] - S["mu"], axis=1) > 1e-9
    touch = np.isin(lay.sm, np.flatnonzero((mi == 2) | (mj == 2)))
    assert np.array_equal(moved, touch)


def test_phi_roundtrip():
    rng = np.random.default_rng(0)
    u = rng.normal(size=(50, 3)); u /= np.linalg.norm(u, axis=1, keepdims=True)
    r = rng.normal(size=(50, 3))
    phi = rng.uniform(-np.pi, np.pi, 50)
    vi = np.zeros((50, 3)); vj = u * 3.0
    _, n1, n2, _ = (np.asarray(a) for a in frames(vi, vj, r, phi))
    est = phi_from_legs(u, r, n1, n2)
    assert np.allclose(np.angle(np.exp(1j * (est - phi))), 0, atol=1e-9)


def test_width_coefficient_calibration():
    """P=2 横向两列高斯条带的遮挡率剖面面积与肢宽之比在 2–8 像素肢宽范围内偏差 ≤5%。"""
    def occ(x, b, sp):
        T = np.ones_like(x)
        for p in range(2):
            c = (p + 0.5) / 2 * b; s = C_WIDTH * b / 4
            ss = np.sqrt(s ** 2 + sp ** 2)
            T *= 1 - 0.98 * (s / ss) * np.exp(-0.5 * ((x - c) / ss) ** 2)
        return 1 - T
    for bpx in (2.0, 3.0, 5.0, 8.0):
        x = np.linspace(-4, bpx + 4, 2000)
        ratio = np.trapezoid(occ(x, bpx, 0.45), x) / bpx
        assert abs(ratio - 1) < 0.05


def test_response_closed_form_vs_monte_carlo():
    """命中能量占比闭式解与光束内蒙特卡洛积分一致。"""
    rng = np.random.default_rng(1)
    mu = np.array([[0.02, 0.01, 10.0]]); t1 = np.array([[1.0, 0, 0]]); t2 = np.array([[0, 0.8, 0.6]])
    s1, s2, al = np.array([0.10]), np.array([0.02]), np.array([0.9])
    o = np.zeros((1, 3)); d = np.array([[0, 0, 1.0]])
    e1, e2 = ray_basis(d)
    h = np.empty(1); tk = np.empty(1)
    sb = 0.015
    FU._resp_fwd(np.array([0]), np.array([0]), mu, t1, t2, s1, s2, al, o, d, e1, e2, np.array([sb]), np.array([0.0]),
                 np.array([1.0]), 0.0, True, h, tk)
    # 蒙特卡洛：光束横截面内高斯分布的子光线，计算面元二维高斯“密度×α”的平均（Σ⊥ 投影近似下的期望占比）
    n = 400000
    P = np.stack([e1[0], e2[0]])
    X = rng.normal(0, sb, (n, 2))
    rho = np.array([mu[0] @ e1[0], mu[0] @ e2[0]])
    A = np.stack([P @ t1[0], P @ t2[0]], 1)
    Sig = A @ np.diag([s1[0] ** 2, s2[0] ** 2]) @ A.T
    dlt = X - rho
    val = al[0] * np.exp(-0.5 * np.einsum("ni,ij,nj->n", dlt, np.linalg.inv(Sig), dlt))
    assert abs(val.mean() - h[0]) < 3e-3


def test_pairs_cover_all_significant_responses():
    rng = np.random.default_rng(2)
    V, mi, mj = _tiny()
    lay = make_layout(V, mi, mj, spacing=0.3)
    m = len(mi)
    S = generate_np(lay, V, np.full(m, 0.08), np.zeros(m), np.zeros(m), np.zeros(m), np.full(m, 3.0))
    o = np.tile([1.0, -12.0, 1.8], (3000, 1)) + rng.normal(0, 0.3, (3000, 3))
    tgt = rng.uniform([-0.2, -0.2, -0.2], [2.2, 0.2, 4.2], (3000, 3))
    d = tgt - o; d /= np.linalg.norm(d, axis=1, keepdims=True)
    pr = build_pairs(S["mu"], S["t1"], 3 * S["s1"], 3 * S["s2"] + 0.05, o, d, np.full(3000, 50.0), np.zeros(3000),
                     np.full(3000, 1e-3), maxk=64)
    e1, e2 = ray_basis(d)
    # 暴力计算全部射线 × 面元响应
    R, Sx = np.meshgrid(np.arange(3000), np.arange(len(S["s1"])), indexing="ij")
    R, Sx = R.ravel(), Sx.ravel()
    h = np.empty(len(R)); tk = np.empty(len(R))
    FU._resp_fwd(R, Sx, S["mu"], S["t1"], S["t2"], S["s1"], S["s2"], S["alpha"], o, d, e1, e2, np.zeros(3000),
                 np.full(3000, 1e-3), np.full(len(R), 1.0), 0.0, True, h, tk)
    # 配对按 3σ 截断（与 3DGS 惯例一致）：响应大于 3σ 处峰值比例 exp(−4.5)≈0.011 的配对必须全部被找到
    sig = h > 0.0115 * S["alpha"][Sx]
    found = set(zip(pr.pr.tolist(), pr.ps.tolist()))
    missing = [(r, s) for r, s in zip(R[sig], Sx[sig]) if (r, s) not in found]
    assert len(missing) == 0


def test_fused_gradient_matches_reference():
    """融合算子（numba 解析反向）与 autograd 参考实现的目标函数与梯度一致。"""
    rng = np.random.default_rng(3)
    V, mi, mj = _tiny()
    m = len(mi)
    lay = make_layout(V, mi, mj, spacing=0.3)
    init = dict(V=V, b=np.full(m, 0.08), phi=rng.normal(0, 0.2, m), d1=np.zeros(m), d2=np.zeros(m),
                logit=np.full(m, 2.0))
    n = 2500
    o = np.tile([1.0, -10.0, 2.0], (n, 1)) + rng.normal(0, 0.5, (n, 3))
    tgt = rng.uniform([-0.2, -0.2, -0.2], [2.2, 0.2, 4.2], (n, 3))
    d = tgt - o; d /= np.linalg.norm(d, axis=1, keepdims=True)
    cam = CamData(o, d, d.copy(), np.zeros((n, 3)), np.zeros(n, np.int64), np.eye(3)[None], rng.random(n),
                  rng.random(n), np.full(n, 0.8), np.ones(n), np.full(n, 3e-4))
    dmeas = np.linalg.norm(tgt - o, axis=1) + rng.normal(0, 0.02, n)
    ret = LidData(o, d, dmeas, 1.3e-3, 0.02)
    free = LidData(o + 0.1, d, np.where(rng.random(n) < 0.5, 40.0, -1.0), 1.3e-3, 0.02)
    prob = Problem(lay, len(V), init, cam, ret, free, Config())
    x = prob.x0() + rng.normal(0, 1e-3, prob.size)
    prob.repair(x)
    from autograd import value_and_grad
    f1, g1 = value_and_grad(lambda z: prob.objective(z))(x)
    f2, g2 = value_and_grad(lambda z: prob.objective_ref(z))(x)
    assert abs(f1 - f2) / abs(f2) < 1e-6
    assert np.linalg.norm(g1 - g2) / np.linalg.norm(g2) < 1e-5


def test_truss_nullity_detects_mechanism():
    V = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1.0]])
    mi = np.array([0, 1, 2, 3, 0]); mj = np.array([1, 2, 3, 0, 2])
    full = np.ones(5, bool)
    no_diag = np.array([True, True, True, True, False])
    n_full = TP.truss_nullity(V, mi, mj, full, fixed_nodes=[0, 1])
    n_nod = TP.truss_nullity(V, mi, mj, no_diag, fixed_nodes=[0, 1])
    assert n_nod > n_full


def test_auc_metric():
    assert ME.auc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) == 1.0
    assert abs(ME.auc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) - 0.5) < 1e-12


def test_section_name_for_width():
    assert ME.section_name_for_width(0.09).startswith("L90x")
    assert ME.section_name_for_width(0.14, prefer_t=0.012) == "L140x12"


def test_cli_help():
    r = subprocess.run([sys.executable, "-m", "anglegs.cli", "--help"], cwd=os.path.dirname(HERE),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "anglegs" in r.stdout
