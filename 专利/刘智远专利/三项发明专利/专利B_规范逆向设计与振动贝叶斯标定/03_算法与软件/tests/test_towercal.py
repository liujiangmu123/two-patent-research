# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
import towercal  # noqa: E402,F401
import towerkit as tk  # noqa: E402
from towercal import bayes, design, excitation, extract, model, oma, pipeline, sensors  # noqa: E402
from towercal.model import ORDER, CAT_A, CAT_I, CAT_J  # noqa: E402


@pytest.fixture(scope="module")
def small():
    g = tk.build_tower("small")
    for a in g.meta["attach"]:
        if a["kind"] == "conductor":
            a["insulator_len"] = 2.5
    di = extract.extract_design_input(g)
    pt = model.ParamTower(g, extract.attach_masses(di))
    return g, di, pt


def test_extract_voltage_and_type(small):
    g, di, _ = small
    assert di.voltage_kV == 220
    assert di.n_conductor_points == 4 and di.n_earthwire_points == 2
    assert abs(di.height_total - g.nodes[:, 2].max()) < 1e-9


def test_extract_angle_tension():
    g = tk.build_tower("suspension")
    nb = [(-400 * np.cos(np.radians(10)), -400 * np.sin(np.radians(10))),
          (400 * np.cos(np.radians(10)), -400 * np.sin(np.radians(10)))]
    di = extract.extract_design_input(g, insulator_len=5.0, neighbor_xy=nb)
    assert abs(di.line_angle_deg - 20.0) < 1e-6
    assert di.tower_type == "tension" and di.voltage_kV == 500
    assert abs(di.span_h - 400) < 1e-6


def test_param_model_matches_towerkit(small):
    g, di, pt = small
    g = g.copy()
    gs = {gr: sec for gr, sec in zip(g.group, g.sec)}      # 组内统一截面（参数化模型按组赋值）
    g.sec = [gs[gr] for gr in g.group]
    fem = tk.fem.FEModel(g, extra_mass=extract.attach_masses(di), mass_factor=model.MASS_FACTOR)
    fem.fix_base()
    f_ref, _ = fem.modes(4)
    f, _ = pt.modes(g.sec, n=4, kappa=1.0, logkv=14.0)        # 基础近似刚性
    assert np.allclose(f, f_ref, rtol=0.02)


def test_kappa_and_foundation_lower_frequency(small):
    _, _, pt = small
    f1, _ = pt.modes(n=3, kappa=1.0, logkv=11.0)
    f2, _ = pt.modes(n=3, kappa=0.7, logkv=9.5)
    assert np.all(f2 < f1)


def test_reduced_model_accuracy(small):
    _, _, pt = small
    rm = model.ReducedModel(pt, [dict(kappa=1.0, logkv=11.0), dict(kappa=0.7, logkv=9.5)])
    A, I, J = pt.group_props()
    fr, _ = rm.eig(A, I, J, 0.85, 10.2, n=6)
    ff, _ = pt.modes(n=6, kappa=0.85, logkv=10.2)
    assert np.max(np.abs(fr - ff) / ff) < 0.01


def test_reverse_design_feasible(small):
    g, di, pt = small
    sc = design.Scenario(kV=220, v0=25.0)
    secs, gs, info = design.reverse_design(g, di, sc, pt=pt)
    Nc, Nt = design.analyse(pt, di, sc, secs)
    r = design.stress_ratios(g, Nc, Nt, secs)
    # 收敛后再分析的应力比应接近控制值（最多一次迭代内力重分布的误差）
    assert r.max() < 1.15
    assert info["changes"][-1] <= 0.05 * g.n_members


def test_prior_pmf(small):
    g, di, pt = small
    pr = design.build_prior(g, di, n_scen=4, rng=0, pt=pt)
    assert np.allclose(pr["pmf"].sum(1), 1.0)
    mix = pipeline.mixture_prior(pt, pr)
    th = mix.sample(50, np.random.default_rng(0))
    assert np.all(np.isfinite(mix.logpdf(th)))


def test_efi_beats_empirical(small):
    g, _, pt = small
    _, phi = pt.modes(n=6, kappa=0.85, logkv=10.2)
    cand = sensors.candidate_nodes(g)
    _, ld_e = sensors.efi_nodes(phi, cand, 6)
    _, ld_m = sensors.efi_nodes(phi, sensors.empirical_nodes(g, 6), 6)
    assert ld_e > ld_m


def test_ssi_cov_two_dof():
    rng = np.random.default_rng(0)
    fs, n = 50.0, 30000
    f0, z0 = np.array([1.2, 3.4]), 0.02
    t = np.arange(n) / fs
    y = np.zeros((n, 2))
    for k, (f, sh) in enumerate(zip(f0, ([1, 0.6], [0.6, -1]))):
        w = 2 * np.pi * f
        from scipy import signal
        b, a = signal.bilinear([1], [1 / w ** 2, 2 * z0 / w, 1], fs)
        q = signal.lfilter(b, a, rng.normal(size=n))
        y += np.outer(q, sh)
    y += 0.02 * y.std() * rng.normal(size=y.shape)
    modes, _ = oma.identify(y, fs, band=(0.5, 6.0), i=20, orders=range(4, 21, 2), min_count=3)
    fid = sorted(m["f"] for m in modes)
    for f in f0:
        assert min(abs(np.array(fid) - f)) / f < 0.03


def test_noise_model_shapes():
    t = np.arange(2000) * 0.05
    acc = np.zeros((2000, 6))
    y, info = excitation.MemsNoise(seed=1).apply(t, acc)
    assert y.shape == acc.shape and len(info["tau_s"]) == 2
    assert 0.5 * info["noise_rms"] < y[:, 0].std() < 50 * info["noise_rms"]


def test_tmcmc_gaussian():
    class P:
        G = 1
        def logpdf(self, th):
            th = np.atleast_2d(th)
            return np.where(np.all(np.abs(th) < 5, 1), 0.0, -np.inf)
        def sample(self, n, rng):
            return rng.uniform(-5, 5, (n, 3))
    ll = lambda th: -0.5 * np.sum(((th - 1.0) / 0.2) ** 2)
    th, _, st, _ = bayes.tmcmc(ll, P(), n=1000, rng=0, n_mh=5)
    assert np.allclose(th.mean(0), 1.0, atol=0.1)
    assert np.allclose(th.std(0), 0.2, atol=0.06)


def test_end_to_end_small(small):
    g, di, pt = small
    pr = design.build_prior(g, di, n_scen=4, rng=1, pt=pt)
    mix = pipeline.mixture_prior(pt, pr)
    rm = pipeline.reduced_model(pt, pr["map"])
    jt = np.array([ORDER.index(pr["map"][gr]) for gr in pt.groups])
    tht = (0.8, 10.0)
    fem = pt.as_femodel({gr: ORDER[j] for gr, j in zip(pt.groups, jt)}, tht)
    sel, _ = pipeline.place_sensors(pt, pr["map"], 6, zmin=5.0)
    t, acc, _, _ = excitation.ambient_response(fem, sensors.node_dofs(sel), duration=400.0, seed=2)
    y, _ = excitation.MemsNoise(seed=2).apply(t, acc)
    modes, _ = pipeline.identify(y, 20.0, band=(0.8, 9.5))
    assert len(modes) >= 2
    res = pipeline.calibrate(pt, rm, modes, sel, mix, n=200, seed=0)
    assert 0.6 <= np.median(res["kappa"]) <= 1.05
    assert np.mean(res["map"] == jt) > 0.4
