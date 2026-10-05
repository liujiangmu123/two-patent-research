import copy
import math
import json
import numpy as np
import pytest

from trusstwin.geometry import section_properties, member_mesh, surface_gaussians, cross_section_world
from trusstwin.observations import project, point_surface_distances, effective_sigma
from trusstwin.mechanics import solve_truss
from trusstwin.pipeline import run_case, demo_case, camera_at


def test_l_section_area_centroid_and_principal_inertia():
    b,t = .100,.010
    p = section_properties(b,t)
    assert p["area_m2"] == pytest.approx(2*b*t-t*t,rel=1e-13)
    centroid = (b*b+b*t-t*t)/(2*(2*b-t))
    assert p["centroid_m"] == pytest.approx([centroid,centroid],rel=1e-13)
    # Independent inclusion-exclusion of two overlapping rectangles.
    raw_x2 = t*b**3/3+b*t**3/3-t**4/3
    expected_i = raw_x2-p["area_m2"]*centroid**2
    raw_xy = b*b*t*t/2-t**4/4
    expected_xy = raw_xy-p["area_m2"]*centroid**2
    assert p["Ixx_m4"] == pytest.approx(expected_i,rel=1e-12)
    assert p["Ixy_m4"] == pytest.approx(expected_xy,rel=1e-12)
    assert p["I_min_m4"] == pytest.approx(expected_i-abs(expected_xy),rel=1e-12)
    assert 0 < p["I_min_m4"] < p["I_max_m4"]


def test_closed_finite_thickness_mesh_volume_and_inner_face():
    mesh = member_mesh([.7,-.2,.3],[.7,-.2,1.5],.1,.008,.31)
    vertices = np.array(mesh["vertices_m"])
    triangles = vertices[np.array(mesh["triangles"])]
    volume = np.einsum("ij,ij->i",triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6
    assert volume == pytest.approx(section_properties(.1,.008)["area_m2"]*1.2,rel=1e-11)
    thin = member_mesh([0,0,0],[0,0,1],.1,.008)
    thick = member_mesh([0,0,0],[0,0,1],.1,.010)
    assert not np.allclose(thin["vertices_m"],thick["vertices_m"])
    p = np.mean(np.array(thin["vertices_m"])[[3,4,10]],axis=0)
    assert point_surface_distances([p],thin)[0] < 1e-12


def test_pinhole_projection_and_invalid_camera():
    camera = {"K":[[1000,0,0],[0,1000,0],[0,0,1]],"R":np.eye(3).tolist(),"t_m":[0,0,10]}
    assert project([[1,2,0]],camera)[0] == pytest.approx([100,200])
    with pytest.raises(ValueError,match="behind"):
        project([[0,0,-11]],camera)
    camera["R"][0][0] = 2
    with pytest.raises(ValueError,match="rotation"):
        project([[0,0,0]],camera)


def test_truss_equilibrium_energy_and_known_vertical_force():
    case = demo_case()
    sections = {m["id"]:{"width_m":m["width_m"],"thickness_m":m["thickness_candidates_m"][-1]} for m in case["members"]}
    result = solve_truss(case["nodes"],case["members"],case["material"],case["supports"],case["loads"],sections)
    assert result["status"] == "solved"
    assert result["member_results"]["M1"]["axial_force_N"] == pytest.approx(-600000,rel=1e-12)
    assert abs(result["member_results"]["M2"]["axial_force_N"]) < 1e-7
    assert result["force_balance_error_N"] < 1e-7
    assert result["free_dof_residual_N"] < 1e-7
    assert result["strain_energy_J"] > 0
    assert result["strain_energy_J"] == pytest.approx(result["external_work_half_J"],rel=1e-12)


def test_remote_ambiguity_screening_split_and_mode_switch():
    result = run_case(demo_case())
    target = next(m for m in result["members"] if m["id"]=="M1")
    assert .45 < target["posterior"][0] < .55
    assert target["status"] == "screening_disagreement"
    assert target["candidates"][0]["utilization_min"] > 1
    assert target["candidates"][1]["utilization_max"] < 1
    actions = [a for a in result["actions"] if a["member_id"]=="M1"]
    assert next(a for a in actions if a["kind"]=="thickness")["effective"] is True
    assert next(a for a in actions if a["kind"]=="image_edge_gap")["effective"] is False
    assert next(a for a in actions if a["kind"]=="lidar_edge_gap")["effective"] is False


def test_thickness_update_removes_mode_switch_requirement():
    result = run_case(demo_case(with_thickness=True))
    target = result["members"][0]
    assert target["posterior"][1] > .999999
    assert target["status"] == "measurement_supported_candidate"
    assert not any(a["effective"] for a in result["actions"] if a["member_id"]=="M1")


def test_joint_lidar_image_fits_physical_width_and_orientation():
    case = demo_case()
    member = case["members"][0]
    member["width_m"] = .090
    member["orientation_rad"] = 0.
    member["thickness_candidates_m"] = [.010]
    member["fit"] = {"width":True,"orientation":True,"width_bounds_m":[.080,.120],"orientation_bounds_rad":[-.4,.4]}
    start,end = case["nodes"]["base"],case["nodes"]["top"]
    surfels = surface_gaussians(start,end,.100,.010,.180,spacing_m=.075)
    points = [s["center_m"] for s in surfels]
    camera = camera_at([4,-4,1.7],[0,0,.5])
    vertices = cross_section_world(start,end,.100,.010,.180)
    pixels = project(vertices,camera).tolist()
    case["measurements"] = [dict(kind="lidar_points",member_id="M1",points_m=points,sigma_m=.00015),
                            dict(kind="image_points",member_id="M1",feature="section_vertices",indices=list(range(6)),pixels=pixels,sigma_px=.05,**camera)]
    result = run_case(case)
    candidate = result["members"][0]["candidates"][0]
    assert candidate["width_m"] == pytest.approx(.100,abs=2e-5)
    assert candidate["orientation_rad"] == pytest.approx(.180,abs=2e-4)
    assert candidate["fit"]["local_rank"] == 2
    assert candidate["chi_square"] < .01


def test_real_missing_member_is_preserved_as_mechanism():
    case = demo_case(); case["members"][0]["exists"] = False
    result = run_case(case)
    assert result["solver"]["status"] == "mechanism_or_unresolved"
    assert result["members"][0]["status"] == "missing_member"
    assert "M1" not in [m["id"] for m in result["geometry"]["members"]]
    assert result["solver"]["mechanics_cases"][0]["analysis"]["free_dof_nullity"] == 1


@pytest.mark.parametrize("change,match",[("units","units"),("material","yield_strength"),("thickness","thickness"),("noise","sigma")])
def test_invalid_inputs_are_rejected(change,match):
    case = demo_case()
    if change=="units": case["units"]="mm-kN-MPa"
    if change=="material": del case["material"]["yield_strength_Pa"]
    if change=="thickness": case["members"][0]["thickness_candidates_m"]=[-.01]
    if change=="noise": case["measurements"][0]["sigma_px"]=0
    with pytest.raises(ValueError,match=match): run_case(case)


def test_ply_and_member_mapping_are_consistent(tmp_path):
    result = run_case(demo_case(),tmp_path)
    content = (tmp_path/"surface_gaussians.ply").read_text()
    assert "property float f_dc_0" in content and "property float rot_3" in content
    count = int(next(line for line in content.splitlines() if line.startswith("element vertex")).split()[-1])
    mapping = json.loads((tmp_path/"gaussian_members.json").read_text())
    assert sum(m["gaussian_count"] for m in mapping)==count==result["geometry"]["gaussian_count"]
    assert mapping[0]["first_gaussian_index"]==0
    assert len(content.split("end_header\n")[1].strip().splitlines())==count


def test_beam_footprint_reduces_lidar_discrimination():
    a = effective_sigma({"kind":"lidar_points","sigma_m":.001,"beam_diameter_m":0})
    b = effective_sigma({"kind":"lidar_points","sigma_m":.001,"beam_diameter_m":.030})
    assert b > 8*a


def test_out_of_library_reading_is_not_forced_to_nearest_candidate():
    case = demo_case()
    case["measurements"] = [dict(kind="thickness",member_id="M1",value_m=.020,sigma_m=.00015)]
    result = run_case(case)
    assert result["engineering_decision"] == "undetermined"
    assert result["members"][0]["status"] == "outside_candidate_library"
    assert result["members"][0]["evidence_summary"]["all_candidates_rejected"]
    assert not result["members"][0]["usable_for_conditional_report"]
    assert result["geometry"]["members"][0]["display_is_conditional"]
    task = next(a for a in result["actions"] if a["member_id"]=="M1")
    assert task["kind"] == "expand_candidate_library_and_review_measurement"
    assert task["requires_review"]


def test_conflicting_precise_thickness_measurements_require_review():
    case = demo_case()
    case["measurements"] = [dict(kind="thickness",member_id="M1",value_m=t,sigma_m=.00015) for t in (.008,.010)]
    result = run_case(case)
    assert result["members"][0]["status"] == "inconsistent_observations"
    assert result["engineering_decision"] == "undetermined"
    assert result["members"][0]["evidence_summary"]["all_candidates_rejected"]
    assert not any(a["effective"] for a in result["actions"] if a["member_id"]=="M1")


def test_prior_only_does_not_remove_observation_equivalent_thickness():
    case = demo_case(); case["members"][0]["candidate_priors"]=[1e10,1.]
    camera = camera_at([30,0,3],[0,0,.5])
    points = [case["nodes"]["base"],case["nodes"]["top"]]
    case["measurements"] = [dict(kind="image_points",member_id="M1",feature="endpoints",indices=[0,1],
                                 pixels=project(points,camera).tolist(),sigma_px=1.,**camera)]
    result = run_case(case); target=result["members"][0]
    assert target["posterior"][0] > .999999
    assert target["likelihood_only_weights"] == pytest.approx([.5,.5])
    assert all(c["retained"] for c in target["candidates"])
    assert target["status"] == "screening_disagreement"
    assert result["engineering_decision"] == "undetermined"


def test_empty_image_correspondences_are_rejected():
    case = demo_case(); case["members"][0]["thickness_candidates_m"]=[.010]
    camera = camera_at([30,0,3],[0,0,.5])
    case["measurements"] = [dict(kind="image_points",member_id="M1",feature="section_vertices",indices=[],pixels=[],sigma_px=1.,**camera)]
    with pytest.raises(ValueError,match="nonempty"):
        run_case(case)


def test_single_section_endpoint_observations_do_not_confirm_thickness():
    case=demo_case(); case["members"][0]["thickness_candidates_m"]=[.010]
    camera=camera_at([30,0,3],[0,0,.5])
    points=[case["nodes"]["base"],case["nodes"]["top"]]
    case["measurements"]=[dict(kind="image_points",member_id="M1",feature="endpoints",indices=[0,1],pixels=project(points,camera).tolist(),sigma_px=1.,**camera)]
    result=run_case(case)
    assert result["members"][0]["status"]=="unverified_single_section_input"
    assert result["engineering_decision"]=="undetermined"


def test_duplicate_measurement_provenance_cannot_manufacture_confidence():
    case=demo_case()
    obs=dict(kind="thickness",member_id="M1",measurement_id="UT-001",value_m=.0095,sigma_m=.001)
    case["measurements"]=[obs]
    result=run_case(case)
    assert result["members"][0]["status"]=="screening_disagreement"
    case["measurements"]=[copy.deepcopy(obs) for _ in range(10)]
    with pytest.raises(ValueError,match="duplicate measurement_id"):
        run_case(case)


def test_empty_measurement_identifier_is_rejected():
    case=demo_case(); case["measurements"][0]["measurement_id"]=" "
    with pytest.raises(ValueError,match="nonempty"):
        run_case(case)


def test_zero_residual_degrees_of_freedom_are_not_support():
    case=demo_case(); case["members"][0]["fit"]={"width":True,"width_bounds_m":[.080,.120]}
    case["measurements"]=[dict(kind="thickness",member_id="M1",value_m=.010,sigma_m=.00015)]
    result=run_case(case)
    assert result["members"][0]["status"]=="insufficient_fit_degrees_of_freedom"
    assert result["engineering_decision"]=="undetermined"


def test_joint_decision_disagreement_survives_equal_marginal_decision_sets():
    nodes={"top":[0.,0.,1.]}
    members=[]
    for i in range(6):
        angle=2*math.pi*i/6
        nodes[f"base{i}"]=[math.cos(angle),math.sin(angle),0.]
        members.append(dict(id=f"M{i}",nodes=[f"base{i}","top"],width_m=.1,thickness_candidates_m=[.008,.010]))
    case={"name":"six distinct hexagonal braces","units":"m-N-Pa","nodes":nodes,"members":members,
          "material":{"E_Pa":200e9,"yield_strength_Pa":355e6},
          "supports":[dict(node=f"base{i}",dofs=[0,1,2]) for i in range(6)],
          "loads":[dict(node="top",force_N=[0,0,-2500000.])],"measurements":[]}
    result=run_case(case)
    assert result["solver"]["joint_candidate_count"]==64
    assert result["joint_disagreement"] and result["unresolved_joint_pair_count"]>0
    assert result["engineering_decision"]=="undetermined"
    assert all(m["candidates"][0]["screening_decisions"]==m["candidates"][1]["screening_decisions"] for m in result["members"])
    actions=[a for a in result["actions"] if a["kind"]=="thickness"]
    assert all(a["effective"] for a in actions)
    assert all(a["separable_pair_count"]>0 and a["unseparated_pair_count"]>0 for a in actions)
    assert all(not a["resolves_all_current_pairs"] for a in actions)
    case["measurements"].append(dict(kind="thickness",member_id="M0",value_m=.010,sigma_m=.00015))
    updated=run_case(case)
    assert updated["joint_disagreement"]
    assert updated["engineering_decision"]=="undetermined"
    assert updated["unresolved_joint_pair_count"]<result["unresolved_joint_pair_count"]
