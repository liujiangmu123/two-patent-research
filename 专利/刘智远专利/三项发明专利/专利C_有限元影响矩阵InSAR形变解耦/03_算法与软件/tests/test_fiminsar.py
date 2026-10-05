import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fiminsar import invert as INV, model as MD, scatter as SC, sim as S, thermal as TH  # noqa: E402


@pytest.fixture(scope="module")
def M():
    return MD.build_model("small")


def test_rigid_translation(M):
    """四腿同步单位竖向位移 → 全塔刚体平移。"""
    u = M.Gb @ np.array([0, 0, 1.0] * 4)
    U = u.reshape(-1, 6)[:, :3]
    assert np.allclose(U[:, 2], 1.0, atol=1e-6) and np.allclose(U[:, :2], 0, atol=1e-6)


def test_thermal_uniform_free_expansion_vertical(M):
    top = int(np.argmax(M.X[:, 2]))
    uz = M.GT1.reshape(-1, 6)[top, 2]
    assert uz > 0 and abs(uz - 1.2e-5 * M.X[top, 2]) / (1.2e-5 * M.X[top, 2]) < 0.5


def test_cr_offset_rotation(M):
    P = M.point_rows([5], [np.array([0.3, 0, 0])])[0]
    u = np.zeros(M.m.ndof); u[6 * 5 + 5] = 0.01      # θz
    assert np.allclose(P @ u, [0, 0.003, 0])


def test_sun_and_shadow(M):
    s = TH.sun_vector(172, 12.0, 29.6)
    assert s[2] > 0.9
    eta = TH.shadow_fraction(M, s)
    assert 0 <= eta.min() and eta.max() <= 1 and eta.mean() > 0.3
    assert TH.irradiance(TH.sun_vector(172, 0.0)) == 0.0


def test_association_recovers_exact():
    Mm = MD.build_model("small")
    g = SC.geometries("FC1")[0]
    c = SC.candidates(Mm, with_cr=True)
    vis = [k for k, x in enumerate(c) if SC.visible(x, g)]
    xyz = np.array([Mm.X[c[k].node] + c[k].offset for k in vis])
    a, p = SC.associate(xyz, c, g, Mm, sigma=(0.2, 0.2, 0.2))
    assert np.mean(a == np.array(vis)) > 0.9


def test_d_optimal_greedy():
    H = np.eye(3)[:, None, :].repeat(1, 1)
    sel, _ = INV.d_optimal(np.vstack([H, H]), 3)
    assert sorted(set(sel) & {0, 1, 2}) == [0, 1, 2] or len(set(np.array(sel) % 3)) == 3


def test_end_to_end_inversion(M):
    ep = S.build_epochs(M, n_per_geom=8, seed=3)
    B = S.settlement_truth(ep.t, (-10, -1, 0, -1), onset=ep.t.mean())
    d = S.synthesize(M, ep, S.Scenario(B=B, noise=0.5, seed=4))
    r, th = S.method_proposed(M, d)
    idx = [E.index for E in d["epochs"]]
    rmse = np.sqrt(np.mean(((r.b - B[idx])[:, [2, 5, 8, 11]] * 1e3) ** 2))
    assert rmse < 3.0
    assert INV.warning_level(1.0) == "正常" and INV.warning_level(6.0) == "紧急"
