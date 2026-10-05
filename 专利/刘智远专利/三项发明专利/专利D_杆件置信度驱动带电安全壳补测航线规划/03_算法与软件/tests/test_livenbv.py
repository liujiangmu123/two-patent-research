# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from livenbv import confidence as C  # noqa: E402
from livenbv import planner as PL  # noqa: E402
from livenbv.safety import SafetyShell, min_distance_dlt409, seg_dist  # noqa: E402
from livenbv.scenario import make_scenario, mirror_maps  # noqa: E402


def test_dlt409_table():
    assert min_distance_dlt409(110) == 1.5
    assert min_distance_dlt409(220) == 3.0
    assert min_distance_dlt409(300) == 4.0
    assert min_distance_dlt409(500) == 5.0


def test_shell_radius_and_violation():
    live = [(np.array([0, -10, 10.0]), np.array([0, 10, 10.0]), "conductor")]
    sh = SafetyShell(live, kv=220, sigma_pos=0.5)
    assert sh.radius == pytest.approx(3.0 + 1.5 + 1.0 + 0.6)
    assert not sh.is_safe([[0, 0, 10 + sh.radius - 0.1]], struct=False)[0]
    assert sh.is_safe([[0, 0, 10 + sh.radius + 0.1]], struct=False)[0]
    v = sh.violations(np.array([[-20, 0, 10.0], [20, 0, 10.0]]))
    assert v["segments"] == 1
    assert sh.violations(np.array([[-20, 0, 30.0], [20, 0, 30.0]]))["segments"] == 0


def test_seg_dist():
    d = seg_dist(np.array([[0, 1, 0.0], [5, 0, 0]]), np.array([0, 0, 0.0]), np.array([1, 0, 0.0]))
    assert np.allclose(d, [1, 4])


def test_predicted_cgeo_monotone_diminishing():
    L = np.array([3.0])
    c = [PL.predicted_cgeo(np.array([n]), np.array([[n / 3, n / 3, n / 3, 0, 0, 0]]), L)[0] for n in (0, 30, 60, 90)]
    assert c[0] < c[1] < c[2] < c[3]
    assert (c[1] - c[0]) > (c[2] - c[1]) > (c[3] - c[2])


@pytest.fixture(scope="module")
def scen():
    return make_scenario("combined", seed=0)


def test_mirror_maps(scen):
    mn, me = mirror_maps(scen.prior)
    assert (mn[0] >= 0).mean() > 0.95
    assert (me[2] >= 0).mean() > 0.95


def test_line_geometry(scen):
    assert sum(1 for s in scen.live if s[2] == "conductor") == 6
    assert len(scen.meta["missing"]) == 8
    assert (~scen.gt_member_exists).sum() == 8


def test_tsp_route_open():
    P = np.array([[0, 0], [1, 0], [2, 0], [3, 0.0]])
    D = np.linalg.norm(P[:, None] - P[None], axis=2)
    r = PL.tsp_route(D, 0, [3, 1, 2])
    assert r == [0, 1, 2, 3]


def test_stop_rule():
    s = PL.StopRule(eps=0.05)
    assert s.check(0.04, 1, 0, 0, 0, 0) == "缺口达标"
    assert s.check(0.2, 1e-6, 0, 0, 0, 0) == "边际增益率过低"
    assert s.check(0.2, 1.0, 0, 0, 0, 0) is None


def test_confidence_fit_intersection():
    # 两根相交直线的点 → 节点交会
    X0 = np.array([[0, 0, 0], [2, 0, 0], [0, 2, 0.0]]) + 0.1
    mi, mj = np.array([0, 0]), np.array([1, 2])
    rng = np.random.default_rng(0)
    t = rng.uniform(0, 1, 200)
    pts = np.concatenate([np.outer(t, [2, 0, 0]), np.outer(t, [0, 2, 0])]) + rng.normal(0, 0.005, (400, 3))
    lab = np.r_[np.zeros(200, int), np.ones(200, int)]
    cen, dirs, ok, _ = C.fit_lines(pts, lab, 2, X0, mi, mj)
    assert ok.all()
    Xn, est = C.intersect_nodes(X0, mi, mj, cen, dirs, ok)
    assert est[0] == 2 and np.linalg.norm(Xn[0]) < 0.02
