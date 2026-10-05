# -*- coding: utf-8 -*-
"""端到端流程：设计输入提取 → 规范逆向设计先验 → 测点优化 → OMA → 贝叶斯修正 → 验算。"""
from __future__ import annotations

import numpy as np

from . import bayes, check, design, extract, model, oma, sensors
from .model import ORDER


def prepare(g, insulator_len=None, neighbor_xy=None, n_scen=16, seed=0):
    di = extract.extract_design_input(g, insulator_len, neighbor_xy)
    pt = model.ParamTower(g, extra_mass=extract.attach_masses(di))
    prior = design.build_prior(g, di, n_scen=n_scen, rng=seed, pt=pt)
    return di, pt, prior


def reduced_model(pt, sections, anchors=((1.0, 11.0), (0.7, 9.4), (0.85, 10.2)), extra_sections=()):
    an = [dict(sections=sections, kappa=k, logkv=v) for k, v in anchors]
    an += [dict(sections=s, kappa=0.85, logkv=10.2) for s in extra_sections]
    return model.ReducedModel(pt, an)


def place_sensors(pt, sections, n_nodes=8, n_modes=8, zmin=10.0, theta=(0.85, 10.2)):
    f, phi = pt.modes(sections, *theta, n=n_modes)
    cand = [c for c in sensors.candidate_nodes(pt.g) if pt.X[c, 2] > zmin]
    sel, ld = sensors.efi_nodes(phi[:, :n_modes], cand, n_nodes)
    return sel, ld


def identify(y, fs, band=(0.8, 7.5), min_count=8, mpc_max=0.2):
    modes, info = oma.identify(y, fs, band=band, i=40, orders=range(10, 81, 2), min_count=min_count)
    modes = [m for m in modes if m["mpc_imag"] < mpc_max]
    # 去重：频率差 <2% 且 MAC>0.9 的保留出现次数多者
    out = []
    for m in sorted(modes, key=lambda m: -m["count"]):
        if all(not (abs(m["f"] - o["f"]) / o["f"] < 0.02 and sensors.mac(m["phi"], o["phi"]) > 0.9) for o in out):
            out.append(m)
    return sorted(out, key=lambda m: m["f"]), info


def calibrate(pt, rm, obs_modes, sensor_nodes, prior, n=600, seed=0, sigma_f=0.01, sigma_mac=0.05, n_model=16,
              kappa=(0.6, 1.05), logkv=(9.0, 11.5)):
    """prior：bayes.MixturePrior / PriorSpec 对象，或 (G, ncat) 先验 pmf 数组。"""
    dofs = sensors.node_dofs(sensor_nodes)
    lik = bayes.ModalLikelihood(rm, obs_modes, rm.free_index(dofs), n_model=n_model, sigma_f=sigma_f,
                                sigma_mac=sigma_mac)
    pr = prior if hasattr(prior, "logpdf") else bayes.PriorSpec(np.asarray(prior), kappa, logkv)
    th, ll, stages, logZ = bayes.tmcmc(lik.loglik, pr, n=n, rng=seed)
    G = len(pt.groups)
    ppmf, mapj, lo, hi = bayes.posterior_sections(th, G)
    return {"samples": th, "loglik": ll, "stages": stages, "logZ": logZ, "pmf": ppmf, "map": mapj, "lo": lo,
            "hi": hi, "kappa": th[:, G], "logkv": th[:, G + 1], "lik": lik}


def mixture_prior(pt, prior, **kw):
    D = [[ORDER.index(d[gr]) for gr in pt.groups] for d in prior["designs"]]
    return bayes.MixturePrior(D, **kw)


def map_theta(res, G):
    """后验点估计：截面取每组离散后验众数，κ 与 log k_v 取后验中位数。"""
    return res["map"], float(np.median(res["kappa"])), float(np.median(res["logkv"]))
