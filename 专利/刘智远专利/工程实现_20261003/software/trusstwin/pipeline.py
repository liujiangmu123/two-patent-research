"""Public, JSON-in/JSON-out engineering prototype API.

run_case(case_dict, output_dir=None) is also used by the local web UI. Input data
association and camera calibration are explicit, fixed inputs. Thickness is
enumerated; width and section orientation may be fitted by scipy least_squares.
"""
from __future__ import annotations
import copy
import itertools
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.special import logsumexp
from scipy.stats import chi2 as chi_square_distribution
from .geometry import section_properties, member_mesh, surface_gaussians, export_gaussian_ply, cross_section_world
from .observations import positive, residuals, feature_prediction, effective_sigma, project
from .mechanics import solve_truss


LIMITATIONS = [
    "The model is a small-strain 3D pin-jointed axial truss, not a full angle-tower beam/connection model or standards-compliance check.",
    "Screening uses gross-section axial yield and weak-axis Euler buckling with the supplied effective-length factor. Local buckling, net-section holes, connections, slip, eccentricity, imperfections and code factors are excluded.",
    "Image/LiDAR association and camera calibration are supplied; raw photographs are not automatically interpreted. The shared-node graph is fixed; fitted continuous parameters are member width and orientation only.",
    "Member existence is a fixed user input, not an implemented missing-member detector. Raw rays, eligible no-return evidence, time synchronization and trajectory estimation are not implemented.",
    "Posterior and likelihood-only weights are conditional/profile weights, not calibrated safety probabilities. Absolute chi-square fit screening assumes declared independent, whitened Gaussian residuals; its nominal p-values are diagnostic and not empirically validated coverage guarantees.",
    "Provided measurement_id values must be unique. Different IDs or missing IDs do not prove independence: repeated points, same acquisition frames and correlated observations require external covariance/whitening or aggregation before this prototype.",
    "Laser footprint is represented by added scalar uncertainty; occlusion, multi-return intensity, scattering and full beam integration are not simulated.",
    "Gaussian PLY contains deterministic finite-thickness engineering surface surfels, with assigned colour/opacity, not a scene trained from real imagery.",
    "The action score is a noise-normalized candidate-separation/cost proxy, not a fully integrated expected value of information.",
]


def _finite_vector(value, size, label):
    vector = np.asarray(value,float)
    if vector.shape!=(size,) or not np.isfinite(vector).all():
        raise ValueError(f"{label} must be a finite {size}-vector")
    return vector.tolist()


def validate_case(case):
    if case.get("units") != "m-N-Pa":
        raise ValueError("units must explicitly equal 'm-N-Pa'; no implicit mm/kN conversion")
    nodes = case.get("nodes")
    if not isinstance(nodes,dict) or len(nodes)<2:
        raise ValueError("nodes must map at least two node IDs to coordinates in metres")
    for key,value in nodes.items():
        _finite_vector(value,3,f"node {key}")
    material = case.get("material",{})
    for field in ("E_Pa","yield_strength_Pa"):
        if field not in material:
            raise ValueError(f"material.{field} is required; no assumed steel grade")
        positive(material[field],f"material.{field}")
    members = case.get("members")
    if not isinstance(members,list) or not members:
        raise ValueError("members must be a nonempty list")
    seen = set()
    for m in members:
        if not isinstance(m.get("id"),str) or m["id"] in seen:
            raise ValueError("member IDs must be unique strings")
        seen.add(m["id"])
        ends = m.get("nodes",[])
        if len(ends)!=2 or ends[0] not in nodes or ends[1] not in nodes:
            raise ValueError(f"member {m['id']} needs two existing shared-node IDs")
        if np.linalg.norm(np.array(nodes[ends[1]])-nodes[ends[0]])<=1e-9:
            raise ValueError("member length must be positive")
        if not isinstance(m.get("exists",True),bool):
            raise ValueError("member.exists must be boolean")
        b = positive(m.get("width_m"),"member.width_m")
        ts = m.get("thickness_candidates_m",[])
        if not ts or len(set(ts))!=len(ts):
            raise ValueError("thickness_candidates_m must be a nonempty unique list")
        for t in ts:
            section_properties(b,t)
        theta = float(m.get("orientation_rad",0.0))
        if not math.isfinite(theta):
            raise ValueError("orientation_rad must be finite")
        positive(m.get("effective_length_factor",1.0),"effective_length_factor")
        prior = m.get("candidate_priors",[1.0]*len(ts))
        if len(prior)!=len(ts) or any(not math.isfinite(float(p)) or p<=0 for p in prior):
            raise ValueError("candidate_priors must be positive and match thickness candidates")
        fit = m.get("fit",{})
        if fit.get("width",False):
            bounds = fit.get("width_bounds_m",[b*.5,b*1.5])
            if len(bounds)!=2 or not max(ts)<bounds[0]<=b<=bounds[1] or bounds[0]>=bounds[1]:
                raise ValueError("width fit bounds must bracket width and be larger than every candidate thickness")
        if fit.get("orientation",False):
            bounds = fit.get("orientation_bounds_rad",[theta-math.pi/2,theta+math.pi/2])
            if len(bounds)!=2 or not bounds[0]<=theta<=bounds[1] or bounds[0]>=bounds[1] or not np.isfinite(bounds).all():
                raise ValueError("orientation fit bounds must bracket orientation_rad")
    if "supports" not in case or "loads" not in case:
        raise ValueError("supports and loads must be explicitly supplied")
    for support in case["supports"]:
        if support.get("node") not in nodes or not support.get("dofs") or any(d not in (0,1,2) for d in support["dofs"]):
            raise ValueError("supports require existing node and explicit dofs from [0,1,2]")
    for load in case["loads"]:
        if load.get("node") not in nodes:
            raise ValueError("load node does not exist")
        _finite_vector(load["force_N"],3,"load.force_N")
    measurement_ids=set()
    for measurement in case.get("measurements",[]):
        if "measurement_id" in measurement:
            mid=measurement["measurement_id"]
            if not isinstance(mid,str) or not mid.strip():
                raise ValueError("measurement_id, when provided, must be a nonempty string")
            if mid in measurement_ids:
                raise ValueError(f"duplicate measurement_id {mid}: repeated evidence must not be counted as independent")
            measurement_ids.add(mid)
        if measurement.get("member_id") not in seen:
            raise ValueError("measurement must identify an existing member")
        effective_sigma(measurement)
        if measurement.get("kind")=="thickness":
            positive(measurement.get("value_m"),"thickness.value_m")
    floor = float(case.get("candidate_probability_floor",.01))
    if not 0<=floor<.5:
        raise ValueError("candidate_probability_floor must be in [0,0.5)")


def _fit_member(member,nodes,measurements):
    start,end = (nodes[key] for key in member["nodes"])
    b0,theta0 = member["width_m"],float(member.get("orientation_rad",0.0))
    fit = member.get("fit",{})
    active = [name for name in ("width","orientation") if fit.get(name,False)]
    lower,upper,initial = [],[],[]
    for name in active:
        bounds = fit.get("width_bounds_m",[b0*.5,b0*1.5]) if name=="width" else fit.get("orientation_bounds_rad",[theta0-math.pi/2,theta0+math.pi/2])
        lower.append(bounds[0]); upper.append(bounds[1]); initial.append(b0 if name=="width" else theta0)
    def parameters(x):
        values = dict(zip(active,x))
        return values.get("width",b0),values.get("orientation",theta0)
    candidates = []
    prior = np.asarray(member.get("candidate_priors",[1.0]*len(member["thickness_candidates_m"])),float)
    prior /= prior.sum()
    for candidate_index,(thickness,p) in enumerate(zip(member["thickness_candidates_m"],prior)):
        def fun(x):
            b,theta = parameters(x)
            values = [residuals(obs,start,end,b,thickness,theta) for obs in measurements]
            return np.concatenate(values) if values else np.zeros(1)
        if active and measurements:
            starts = [np.array(initial)]
            if "orientation" in active:
                j = active.index("orientation")
                for offset in (-.35,.35):
                    x = np.array(initial); x[j] = np.clip(x[j]+offset,lower[j]+1e-9,upper[j]-1e-9); starts.append(x)
            options = [least_squares(fun,x,bounds=(lower,upper),max_nfev=180,xtol=1e-10,ftol=1e-10,gtol=1e-9) for x in starts]
            solved = min(options,key=lambda r:float(r.fun@r.fun))
            values = solved.fun; b,theta = parameters(solved.x)
            singular = np.linalg.svd(solved.jac,compute_uv=False)
            rank = int(np.sum(singular>max(float(singular.max(initial=0)),1.)*1e-7))
            optimizer = {"success":bool(solved.success),"status":int(solved.status),"nfev":int(solved.nfev),
                         "parameters":active,"whitened_jacobian_singular_values":singular.tolist(),
                         "local_rank":rank,"local_rank_deficient":rank<len(active),
                         "at_parameter_bounds":bool(np.any(np.isclose(solved.x,lower,atol=1e-8,rtol=1e-6)) or np.any(np.isclose(solved.x,upper,atol=1e-8,rtol=1e-6)))}
        else:
            values = fun([]); b,theta = b0,theta0
            optimizer = {"success":True,"parameters":active if not measurements else [],"nfev":0,"local_rank":0,
                         "local_rank_deficient":bool(active and not measurements),"at_parameter_bounds":False,
                         "note":"geometry parameters fixed" if not active else "no observations; parameters remain at input values"}
        chi2 = float(values@values)
        residual_count = len(values) if measurements else 0
        dof = residual_count-len(optimizer["parameters"])
        nominal_p = float(chi_square_distribution.sf(chi2,dof)) if dof>0 else None
        candidates.append({"candidate_id":f"{member['id']}:C{candidate_index}","thickness_m":float(thickness),"width_m":float(b),"orientation_rad":float(theta),
                           "chi_square":chi2,"residual_count":residual_count,"fit_degrees_of_freedom":dof,
                           "nominal_fit_p_value":nominal_p,"prior_probability":float(p),
                           "log_weight":math.log(float(p))-.5*chi2,"fit":optimizer,
                           "section_properties":section_properties(b,thickness),"mechanics":[]})
    normalizer = float(logsumexp([c["log_weight"] for c in candidates]))
    likelihood_normalizer = float(logsumexp([-.5*c["chi_square"] for c in candidates]))
    for c in candidates:
        c["probability"] = math.exp(c["log_weight"]-normalizer)
        c["likelihood_probability"] = math.exp(-.5*c["chi_square"]-likelihood_normalizer)
    return candidates


def camera_at(eye,target,focal_px=1800.0):
    eye,target = np.asarray(eye,float),np.asarray(target,float)
    forward = target-eye; forward /= np.linalg.norm(forward)
    up = np.array([0.,0.,1.])
    if abs(forward@up)>.99:
        up = np.array([0.,1.,0.])
    right = np.cross(forward,up); right /= np.linalg.norm(right)
    down = np.cross(forward,right)
    R = np.stack([right,down,forward])
    return {"K":[[focal_px,0,960],[0,focal_px,540],[0,0,1]],"R":R.tolist(),"t_m":(-R@eye).tolist()}


def _actions(case,member,candidates,disagreement,joint_conflicts=None):
    nodes = case["nodes"]; start,end = (nodes[key] for key in member["nodes"])
    middle = (np.array(start)+end)/2
    templates = [a for a in case.get("planned_actions",[]) if a.get("member_id")==member["id"]]
    if not templates:
        nominal = candidates[0]
        polygon = cross_section_world(start,end,nominal["width_m"],nominal["thickness_m"],nominal["orientation_rad"])
        scan = polygon[3]-polygon[0]; scan /= np.linalg.norm(scan)
        templates = [dict(kind="image_edge_gap",member_id=member["id"],sigma_px=1.2,cost_units=1.,
                          **camera_at(middle+[30.,0.,5.],middle)),
                     dict(kind="lidar_edge_gap",member_id=member["id"],sigma_m=.01,beam_diameter_m=.03,
                          scan_direction=scan.tolist(),cost_units=2.),
                     dict(kind="thickness",member_id=member["id"],sigma_m=.00015,cost_units=8.)]
    floor = case.get("candidate_probability_floor",.01)
    if joint_conflicts is None:
        pairs = [(a,b,f"local_{i}",a["likelihood_probability"]*b["likelihood_probability"])
                 for i,(a,b) in enumerate(itertools.combinations(candidates,2))
                 if a["retained"] and b["retained"] and a.get("screening_decisions")!=b.get("screening_decisions")]
    else:
        lookup = {c["candidate_id"]:c for c in candidates}
        pairs = [(lookup[p["a_candidates"][member["id"]]],lookup[p["b_candidates"][member["id"]]],p["id"],p["likelihood_pair_weight"])
                 for p in joint_conflicts]
    threshold = positive(case.get("measurement_separation_threshold",3.),"measurement_separation_threshold")
    results = []
    for n,template in enumerate(templates):
        sigma = effective_sigma(template)
        distances,cache = [],{}
        for a,b,pair_id,pair_weight in pairs:
            key = (a["candidate_id"],b["candidate_id"])
            if key not in cache:
                pa = feature_prediction(template,start,end,a["width_m"],a["thickness_m"],a["orientation_rad"])
                pb = feature_prediction(template,start,end,b["width_m"],b["thickness_m"],b["orientation_rad"])
                cache[key] = float(np.linalg.norm(pa-pb)/sigma)
            distances.append((pair_id,cache[key],pair_weight))
        separable = [p for p,d,w in distances if d>=threshold]
        unseparated = [p for p,d,w in distances if d<threshold]
        separation = min((d for p,d,w in distances if d>=threshold),default=0.)
        effective = bool(disagreement and separable)
        cost = positive(template.get("cost_units",1.),"action cost_units")
        total_weight = sum(w for p,d,w in distances)
        covered_weight = sum(w for p,d,w in distances if d>=threshold)
        fraction = covered_weight/total_weight if total_weight>0 else 0.
        score = fraction*(separation*separation/(1+separation*separation))/cost if effective else 0.
        reason = ("No retained joint-candidate pair changes the declared screening decision vector." if not disagreement or not distances
                  else f"Can separate {len(separable)} of {len(distances)} conflicting joint pairs at the {threshold:.3f}-sigma threshold; {len(unseparated)} pairs remain unseparated by this action. "
                       +("Additional member measurements may be required." if effective and unseparated else "Resolution/noise is insufficient; another measurement mode is required." if not effective else "All current modeled conflicting pairs are separable by this action."))
        results.append({"id":template.get("id",f"{member['id']}_action_{n}"),"kind":template["kind"],"member_id":member["id"],
                        "score":score,"effective":effective,"reason":reason,"separation_sigma":separation,
                        "required_separation_sigma":threshold,"cost_units":cost,"measurement_template":copy.deepcopy(template),
                        "separable_joint_pair_ids":separable,"unseparated_joint_pair_ids":unseparated,
                        "separable_pair_count":len(separable),"unseparated_pair_count":len(unseparated),
                        "weighted_conflict_pair_coverage":fraction,"resolves_all_current_pairs":bool(separable and not unseparated)})
    return sorted(results,key=lambda x:x["score"],reverse=True)


def run_case(case_dict,output_dir=None):
    case = copy.deepcopy(case_dict); validate_case(case)
    nodes,members = case["nodes"],case["members"]
    all_candidates = {}
    for member in members:
        measurements = [m for m in case.get("measurements",[]) if m["member_id"]==member["id"]]
        all_candidates[member["id"]] = _fit_member(member,nodes,measurements)
    fit_alpha = float(case.get("nominal_fit_rejection_alpha",.001))
    if not 0 < fit_alpha < .1:
        raise ValueError("nominal_fit_rejection_alpha must be in (0,0.1)")
    for candidates in all_candidates.values():
        for c in candidates:
            c["absolute_fit_consistent"] = (c["nominal_fit_p_value"]>=fit_alpha) if c["nominal_fit_p_value"] is not None else None
        any_consistent = any(c["absolute_fit_consistent"] is True for c in candidates)
        for c in candidates:
            c["retained"] = (c["likelihood_probability"]>=case.get("candidate_probability_floor",.01)
                             and (c["absolute_fit_consistent"] is not False or not any_consistent))
    active = [m for m in members if m.get("exists",True)]
    combinations = math.prod(len(all_candidates[m["id"]]) for m in active)
    if combinations>int(case.get("max_joint_candidates",4096)):
        raise ValueError(f"{combinations} joint section combinations exceed the declared enumeration budget; reduce candidates or partition the case explicitly")
    mechanics_cases = []
    for combination in itertools.product(*(all_candidates[m["id"]] for m in active)):
        sections = {m["id"]:c for m,c in zip(active,combination)}
        analysis = solve_truss(nodes,members,case["material"],case["supports"],case["loads"],sections)
        weight = math.prod(c["probability"] for c in combination)
        decision_vector = {m["id"]:analysis["member_results"][m["id"]]["decision"] for m in active} if analysis["status"]=="solved" else {}
        mechanics_cases.append({"id":f"J{len(mechanics_cases):04d}","weight":weight,
                                "likelihood_weight":math.prod(c["likelihood_probability"] for c in combination),
                                "sections":{k:v["thickness_m"] for k,v in sections.items()},
                                "candidate_ids":{k:v["candidate_id"] for k,v in sections.items()},
                                "decision_vector":decision_vector,"analysis":analysis,
                                "observation_admissible":all(c["retained"] and c["absolute_fit_consistent"] is not False for c in combination)})
        for m,c in zip(active,combination):
            if analysis["status"]=="solved" and mechanics_cases[-1]["observation_admissible"]:
                c["mechanics"].append(analysis["member_results"][m["id"]])
    solved = [m for m in mechanics_cases if m["analysis"]["status"]=="solved"]
    solver_status = "solved" if len(solved)==len(mechanics_cases) else "mechanism_or_unresolved"
    joint_eligible = [m for m in solved if m["observation_admissible"]]
    pair_budget = int(case.get("max_joint_pair_checks",50000))
    if len(joint_eligible)*(len(joint_eligible)-1)//2>pair_budget:
        raise ValueError("Joint decision-pair comparison exceeds max_joint_pair_checks; explicitly partition/reduce the case or raise its resource budget. No agreement or stop decision was inferred.")
    joint_conflicts = []
    for a,b in itertools.combinations(joint_eligible,2):
        if a["decision_vector"]!=b["decision_vector"]:
            joint_conflicts.append({"id":f"P{len(joint_conflicts):05d}","a_joint_id":a["id"],"b_joint_id":b["id"],
                                    "a_candidates":a["candidate_ids"],"b_candidates":b["candidate_ids"],
                                    "changed_decision_members":[m["id"] for m in active if a["decision_vector"][m["id"]]!=b["decision_vector"][m["id"]]],
                                    "likelihood_pair_weight":a["likelihood_weight"]*b["likelihood_weight"]})
    joint_disagreement = bool(joint_conflicts)
    output_members,actions,geometry_members,all_surfels,mapping = [],[],[],[],[]
    unresolved_reasons = []
    for member in members:
        candidates = all_candidates[member["id"]]
        exists = member.get("exists",True)
        member_observations = [obs for obs in case.get("measurements",[]) if obs["member_id"]==member["id"]]
        fit_alpha = float(case.get("nominal_fit_rejection_alpha",.001))
        if not 0 < fit_alpha < .1:
            raise ValueError("nominal_fit_rejection_alpha must be in (0,0.1)")
        for c in candidates:
            c["absolute_fit_consistent"] = (c["nominal_fit_p_value"]>=fit_alpha) if c["nominal_fit_p_value"] is not None else None
        any_consistent = any(c["absolute_fit_consistent"] is True for c in candidates)
        has_effective_residuals = any(c["residual_count"]>0 for c in candidates)
        all_bad = has_effective_residuals and all(c["absolute_fit_consistent"] is False for c in candidates)
        thickness_obs = [obs for obs in member_observations if obs["kind"]=="thickness"]
        conflict = any(abs(a["value_m"]-b["value_m"])/math.sqrt(a["sigma_m"]**2+b["sigma_m"]**2)>6
                       for a,b in itertools.combinations(thickness_obs,2))
        library_low,library_high = min(c["thickness_m"] for c in candidates),max(c["thickness_m"] for c in candidates)
        outside_library = any(obs["value_m"]+3*obs["sigma_m"]<library_low or obs["value_m"]-3*obs["sigma_m"]>library_high for obs in thickness_obs)
        for c in candidates:
            values = [v["utilization"] for v in c["mechanics"]]
            c["utilization_min"] = min(values) if values else None
            c["utilization_max"] = max(values) if values else None
            c["screening_decisions"] = sorted({v["decision"] for v in c["mechanics"]})
            # A strong prior must not remove an observation-equivalent alternative.
            # All-bad cases preserve diagnostics; they never acquire engineering eligibility.
            c["retained"] = (c["likelihood_probability"]>=case.get("candidate_probability_floor",.01)
                             and (c["absolute_fit_consistent"] is not False or not any_consistent))
        retained = [c for c in candidates if c["retained"]]
        decision_sets = {tuple(c["screening_decisions"]) for c in retained}
        disagreement = (len(decision_sets)>1 or any(member["id"] in p["changed_decision_members"] for p in joint_conflicts)) and bool(solved)
        if not exists:
            status = "missing_member"
        elif solver_status!="solved":
            status = "structural_model_unresolved"
        elif conflict:
            status = "inconsistent_observations"
        elif outside_library:
            status = "outside_candidate_library"
        elif all_bad:
            status = "observation_model_mismatch"
        elif has_effective_residuals and not any_consistent:
            status = "insufficient_fit_degrees_of_freedom"
        elif any(c["fit"].get("at_parameter_bounds") for c in retained):
            status = "parameter_bound_warning"
        elif any(c["fit"].get("local_rank_deficient") for c in retained):
            status = "local_identifiability_warning"
        elif disagreement:
            status = "screening_disagreement"
        elif len(candidates)==1 and not thickness_obs and member.get("section_source") not in ("verified_as_built","synthetic_known_input"):
            status = "unverified_single_section_input"
        elif len(candidates)==1 and not has_effective_residuals:
            status = "input_fixed_section"
        elif len(retained)==1 and any_consistent and has_effective_residuals:
            status = "measurement_supported_candidate"
        else:
            status = "geometric_ambiguity_same_screening_decision"
        # Select the display by measurement-only fit; prior is separately visible.
        chosen = max(candidates,key=lambda c:c["likelihood_probability"])
        usable = status in ("input_fixed_section","measurement_supported_candidate")
        if not usable:
            unresolved_reasons.append(f"{member['id']}: {status}")
        start,end = (nodes[key] for key in member["nodes"])
        utilization_values = [v["utilization"] for c in retained for v in c["mechanics"]]
        public_candidates = [{k:v for k,v in c.items() if k not in ("mechanics","log_weight")} for c in candidates]
        output_members.append({"id":member["id"],"endpoints":[start,end],"node_ids":member["nodes"],
                               "width":chosen["width_m"],"width_m":chosen["width_m"],"orientation_rad":chosen["orientation_rad"],
                               "thickness_candidates":[c["thickness_m"] for c in candidates],"posterior":[c["probability"] for c in candidates],
                               "likelihood_only_weights":[c["likelihood_probability"] for c in candidates],
                               "prior_weights":[c["prior_probability"] for c in candidates],
                               "candidates":public_candidates,"status":status,"exists":exists,
                               "section_source":member.get("section_source","unspecified"),
                               "usable_for_conditional_report":usable,
                               "evidence_summary":{"has_effective_residuals":has_effective_residuals,"any_absolute_fit_consistent":any_consistent,
                                                   "all_candidates_rejected":all_bad,"conflicting_thickness_observations":conflict,
                                                   "outside_candidate_library":outside_library,
                                                   "fit_test":"nominal chi-square diagnostic under declared independent whitened Gaussian residuals",
                                                   "rejection_alpha":fit_alpha,"no_safety_probability_claim":True},
                               "utilization":{"minimum":min(utilization_values) if utilization_values else None,
                                              "maximum":max(utilization_values) if utilization_values else None,
                                              "definition":"conditional gross-yield/Euler axial screening; not code compliance"}})
        if exists:
            review_statuses = {"inconsistent_observations","outside_candidate_library","observation_model_mismatch",
                               "insufficient_fit_degrees_of_freedom","parameter_bound_warning","local_identifiability_warning","unverified_single_section_input"}
            if status in review_statuses:
                kind = ("verify_section_assumption" if status=="unverified_single_section_input" else
                        "expand_candidate_library_and_review_measurement" if outside_library and not conflict else "review_observation_model_and_repeat_measurement")
                actions.append({"id":f"{member['id']}_review","kind":kind,"member_id":member["id"],"score":1.,
                                "effective":False,"requires_review":True,
                                "reason":f"{status}: do not select an existing section. Review calibration, association, noise and geometry/candidate bounds; repeat conflicting measurements or expand the candidate library."})
            else:
                actions.extend(_actions(case,member,candidates,joint_disagreement,joint_conflicts))
            mesh = member_mesh(start,end,chosen["width_m"],chosen["thickness_m"],chosen["orientation_rad"])
            geometry_members.append({"id":member["id"],"endpoints":[start,end],"display_candidate_thickness_m":chosen["thickness_m"],
                                     "display_is_conditional":len(retained)>1 or not usable or status=="input_fixed_section","mesh":mesh})
            geometry_members[-1]["display_observation_model_valid"] = any_consistent if has_effective_residuals else None
            surfels = surface_gaussians(start,end,chosen["width_m"],chosen["thickness_m"],chosen["orientation_rad"],case.get("gaussian_spacing_m",.10))
            offset = len(all_surfels); all_surfels.extend(surfels)
            mapping.append({"member_id":member["id"],"first_gaussian_index":offset,"gaussian_count":len(surfels),
                            "thickness_m":chosen["thickness_m"],"width_m":chosen["width_m"],"orientation_rad":chosen["orientation_rad"]})
    balance = max((m["analysis"]["force_balance_error_N"] for m in solved),default=None)
    result = {"schema_version":"trusstwin.case-result/0.1","name":case.get("name","unnamed case"),"units":"m-N-Pa",
              "engineering_decision":"undetermined" if unresolved_reasons or joint_disagreement or not case.get("measurements") else "report_conditionally",
              "engineering_decision_reasons":unresolved_reasons or (["No observations were supplied; computed capacities are assumptions only."] if not case.get("measurements") else ["Report only under the declared geometry, material, load and simplified-truss assumptions; no standards-compliance conclusion."]),
              "joint_disagreement":joint_disagreement,"unresolved_joint_pair_count":len(joint_conflicts),
              "members":output_members,"actions":sorted(actions,key=lambda x:x["score"],reverse=True),
              "geometry":{"nodes":[{"id":k,"position_m":v} for k,v in nodes.items()],"members":geometry_members,
                          "gaussian_count":len(all_surfels),"gaussian_members":mapping,
                          "representation":"finite-thickness deterministic engineering surfaces; no image-trained scene"},
              "measurements":case.get("measurements",[]),"material":case["material"],"supports":case["supports"],"loads":case["loads"],
              "measurement_independence":{"identified_measurement_count":sum("measurement_id" in obs for obs in case.get("measurements",[])),
                                          "unidentified_measurement_count":sum("measurement_id" not in obs for obs in case.get("measurements",[])),
                                          "assumption":"Unique IDs are not proof of independence; declared scalar noises assume external de-correlation/whitening. No automatic correlation estimation is implemented."},
              "solver":{"status":solver_status,"model":"linear 3D pin-jointed axial truss",
                        "inference":"discrete thickness enumeration with optional profiled least-squares width/orientation; fixed shared nodes and calibration",
                        "joint_candidate_count":combinations,"solved_candidate_count":len(solved),
                        "admissible_joint_candidate_count":len(joint_eligible),"joint_conflicting_pairs":joint_conflicts,
                        "force_balance_error_N":balance,"mechanics_cases":mechanics_cases,
                        "probability_semantics":"conditional Gaussian/profile likelihood weights, not empirical safety confidence"},
              "limitations":LIMITATIONS.copy(),"case":case}
    if output_dir is not None:
        directory = Path(output_dir); directory.mkdir(parents=True,exist_ok=True)
        export_gaussian_ply(directory/"surface_gaussians.ply",all_surfels)
        (directory/"gaussian_members.json").write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding="utf-8")
        result["artifacts"] = {"gaussians":"surface_gaussians.ply","mapping":"gaussian_members.json","result":"result.json"}
        (directory/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return result


def demo_case(with_thickness=False):
    """Known synthetic tripod: only the vertical member carries the vertical load.

    Same width, 8/10 mm hypotheses remain remotely ambiguous at the declared
    resolution; 10 mm measurement resolves them. This is not a measured tower.
    """
    nodes = {"base":[0.,0.,0.],"top":[0.,0.,1.],"brace_x":[1.,0.,0.],"brace_y":[0.,1.,0.]}
    members = [dict(id="M1",nodes=["base","top"],width_m=.1,thickness_candidates_m=[.008,.010],orientation_rad=0.,effective_length_factor=1.),
               dict(id="M2",nodes=["brace_x","top"],width_m=.1,thickness_candidates_m=[.012],orientation_rad=0.,effective_length_factor=1.),
               dict(id="M3",nodes=["brace_y","top"],width_m=.1,thickness_candidates_m=[.012],orientation_rad=0.,effective_length_factor=1.)]
    for member in members[1:]:
        member["section_source"]="synthetic_known_input"
    camera = camera_at([30.,0.,3.],[0.,0.,.5])
    cross = cross_section_world(nodes["base"],nodes["top"],.1,.010,0.)
    images = project(cross[[0,3]],camera).tolist()
    mesh = member_mesh(nodes["base"],nodes["top"],.1,.010,0.)
    v = np.asarray(mesh["vertices_m"])
    points = [(v[0]+v[1]+v[7])/3,(v[5]+v[0]+v[6])/3,(v[3]+v[4]+v[10])/3]
    measurements = [dict(kind="image_points",member_id="M1",feature="section_vertices",indices=[0,3],pixels=images,sigma_px=1.2,**camera),
                    dict(kind="lidar_points",member_id="M1",points_m=[p.tolist() for p in points],sigma_m=.015,beam_diameter_m=.03)]
    if with_thickness:
        measurements.append(dict(kind="thickness",member_id="M1",value_m=.010,sigma_m=.00015))
    return {"name":"Synthetic finite-thickness angle/truss measurement demonstration","units":"m-N-Pa","nodes":nodes,"members":members,
            "material":{"name":"explicit demo material","E_Pa":200e9,"yield_strength_Pa":355e6},
            "supports":[dict(node=n,dofs=[0,1,2]) for n in ("base","brace_x","brace_y")],
            "loads":[dict(node="top",force_N=[0.,0.,-600000.])],"measurements":measurements,
            "candidate_probability_floor":.01,"measurement_separation_threshold":3.,"gaussian_spacing_m":.1}


def geometry_demo_case():
    """Synthetic calibrated geometry fitting example; thickness stays ambiguous."""
    case=demo_case()
    case["name"]="Synthetic calibrated LiDAR/image joint geometry fit; NOT field data"
    member=case["members"][0]
    member["width_m"]=.09; member["orientation_rad"]=0.
    member["fit"]={"width":True,"orientation":True,"width_bounds_m":[.080,.120],"orientation_bounds_rad":[-.4,.4]}
    start,end=case["nodes"]["base"],case["nodes"]["top"]
    surfels=surface_gaussians(start,end,.100,.010,.180,spacing_m=.075)
    points=[s["center_m"] for s in surfels][::3]
    camera=camera_at([8,-8,1.7],[0,0,.5])
    vertices=cross_section_world(start,end,.100,.010,.180)
    case["measurements"]=[dict(kind="lidar_points",member_id="M1",points_m=points,sigma_m=.003,beam_diameter_m=.012),
                          dict(kind="image_points",member_id="M1",feature="section_vertices",indices=list(range(6)),pixels=project(vertices,camera).tolist(),sigma_px=1.2,**camera)]
    case["synthetic_ground_truth"]={"member_id":"M1","width_m":.100,"thickness_m":.010,"orientation_rad":.180,
                                   "note":"Generated noiseless feature means with declared nonzero uncertainty; not real or independently calibrated data."}
    return case
