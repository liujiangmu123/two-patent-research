"""3D pin-jointed linear axial-truss FE and a declared screening limit state.

This solver excludes beam bending, connection eccentricity, joint slip, local
buckling, corrosion distribution, net-section holes and code partial factors.
It must never be reported as a complete standards-compliance verification.
"""
from __future__ import annotations
import math
import numpy as np
from .geometry import section_properties


def solve_truss(nodes, members, material, supports, loads, sections) -> dict:
    ids = list(nodes); index = {key:i for i,key in enumerate(ids)}
    size = 3*len(ids); K = np.zeros((size,size)); f = np.zeros(size)
    E,fy = material["E_Pa"],material["yield_strength_Pa"]
    active = []
    for member in members:
        if not member.get("exists",True):
            continue
        start,end = member["nodes"]
        delta = np.array(nodes[end])-nodes[start]
        length = float(np.linalg.norm(delta)); direction = delta/length
        section = sections[member["id"]]
        prop = section_properties(section["width_m"],section["thickness_m"])
        kg = E*prop["area_m2"]/length*np.outer(direction,direction)
        dofs = np.r_[np.arange(3*index[start],3*index[start]+3),np.arange(3*index[end],3*index[end]+3)]
        K[np.ix_(dofs,dofs)] += np.block([[kg,-kg],[-kg,kg]])
        active.append((member,length,direction,dofs,prop))
    for load in loads:
        p = 3*index[load["node"]]; f[p:p+3] += load["force_N"]
    fixed = sorted({3*index[s["node"]]+d for s in supports for d in s["dofs"]})
    free = np.array([i for i in range(size) if i not in fixed],int)
    u = np.zeros(size)
    kff = K[np.ix_(free,free)]
    if len(free):
        eig = np.linalg.eigvalsh(kff)
        scale = max(float(np.max(np.abs(eig))),1.0)
        nullity = int(np.sum(eig <= scale*1e-10))
        if nullity:
            return {"status":"mechanism", "free_dof_nullity":nullity,
                    "reason":"The supplied graph and supports have unconstrained modes; no missing member was inserted.",
                    "member_results":{}}
        u[free] = np.linalg.solve(kff,f[free])
    reactions = K@u-f
    result = {}
    for member,length,direction,dofs,prop in active:
        axial = E*prop["area_m2"]/length*float(direction@(u[dofs[3:]]-u[dofs[:3]]))
        yield_capacity = fy*prop["area_m2"]
        factor = float(member.get("effective_length_factor",1.0))
        euler = math.pi**2*E*prop["I_min_m4"]/(factor*length)**2
        capacity = min(yield_capacity,euler) if axial < 0 else yield_capacity
        result[member["id"]] = {"axial_force_N":axial,"mode":"compression" if axial<0 else "tension",
                                "yield_capacity_N":yield_capacity,"euler_weak_axis_capacity_N":euler,
                                "screening_capacity_N":capacity,"utilization":abs(axial)/capacity,
                                "decision":"below_screening_limit" if abs(axial)/capacity<=1 else "exceeds_screening_limit"}
    imbalance = f.reshape(-1,3).sum(axis=0)+reactions.reshape(-1,3).sum(axis=0)
    return {"status":"solved","free_dof_nullity":0,
            "displacements_m":{key:u[3*i:3*i+3].tolist() for i,key in enumerate(ids)},
            "reactions_N":{key:reactions[3*i:3*i+3].tolist() for i,key in enumerate(ids)},
            "force_balance_error_N":float(np.linalg.norm(imbalance)),
            "free_dof_residual_N":float(np.linalg.norm(reactions[free])),
            "strain_energy_J":float(.5*u@K@u),"external_work_half_J":float(.5*f@u),
            "member_results":result}
