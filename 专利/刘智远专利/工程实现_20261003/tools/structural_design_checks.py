"""Design calculations only; this script does not invoke CAD or fabricate test results."""
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
p = json.loads((PACKAGE/'mechanical/design_parameters.json').read_text(encoding='utf-8'))
a = p['calculation_assumptions']
outer,wall = (p['frame_profile_mm'][k]/1000 for k in ('outer','wall'))
inner = outer-2*wall
area = outer**2-inner**2
inertia = (outer**4-inner**4)/12
main_lengths = [length/1000 for length in p['main_profile_cut_lengths_mm']]
brace_lengths = [sum(((b-a)/1000)**2 for a,b in zip(start,end))**.5
                 for start,end in p['brace_centerline_endpoints_mm']]
brace_outer,brace_wall = (p['brace_profile_mm'][k]/1000 for k in ('outer','wall'))
brace_area = brace_outer**2-(brace_outer-2*brace_wall)**2
small_arm_lengths = [length/1000 for length in p['coupon_arm_lengths_mm']+p['reference_target_arm_lengths_mm']]
frame_mass = (area*sum(main_lengths)+brace_area*(sum(brace_lengths)+sum(small_arm_lengths)))*a['aluminum_density_kg_m3']
coupon_masses = []
for c in p['coupon_nominal_mm']:
    b,t,L = (c[k]/1000 for k in ('width','thickness','length'))
    coupon_masses.append({'id':c['id'],'mass_kg':(2*b*t-t*t)*L*c['mass_density_kg_m3']})
mass = frame_mass + sum(c['mass_kg'] for c in coupon_masses) + sum(v for k,v in p['mass_allowance_kg'].items() if k!='ballast_optional')
lever = min(abs(xy[1]) for xy in p['feet']['centers_xy_mm'])/1000-a['center_of_gravity_offset_limit_m']
restoring = a['minimum_verified_rig_mass_kg']*9.80665*lever
def wind(v):
    force=.5*a['air_density_kg_m3']*v*v*a['drag_coefficient']*a['projected_area_m2']*a['gust_factor']
    moment=force*a['wind_application_height_m']
    deflection=(force/2)*(p['upright_height_above_base_mm']/1000)**3/(3*a['aluminum_E_Pa']*inertia)
    return {'speed_m_s':v,'force_N':force,'overturning_moment_Nm':moment,'restoring_moment_Nm':restoring,
            'overturning_factor':restoring/moment,'upright_tip_upper_bound_m':deflection,
            'overturning_requirement_met':restoring/moment>=a['minimum_overturning_factor'],
            'deflection_requirement_met':deflection<=a['maximum_support_tip_deflection_m']}
small_inertia=(brace_outer**4-(brace_outer-2*brace_wall)**4)/12
arm_force=3*9.80665
arm_deflection=arm_force*.15**3/(3*a['aluminum_E_Pa']*small_inertia)
poisson_ratio=.33  # preliminary aluminum assumption; supplier and joint stiffness pending
shear_modulus=a['aluminum_E_Pa']/(2*(1+poisson_ratio))
mid_side=brace_outer-brace_wall
torsion_constant=4*(mid_side**2)**2/(4*mid_side/brace_wall)
arm_torque=arm_force*.05
arm_twist=arm_torque*.15/(shear_modulus*torsion_constant)
coupon_edge_displacement=arm_twist*.1
# Conservative allowance placement at rear upright y=230 mm; actual positions must be measured.
y_moment=(area*(1.3+.4)*a['aluminum_density_kg_m3']*.23
          + sum(c['mass_kg'] for c in coupon_masses)*.12
          + brace_area*a['aluminum_density_kg_m3']*sum(length*(p['short_arm_start_y_mm']/1000-length/2) for length in small_arm_lengths)
          + p['mass_allowance_kg']['brackets_and_fasteners']*.23)
ballast=p['mass_allowance_kg']['ballast_optional']
cg_with_ballast=(y_moment+ballast*p['ballast_center_mm'][1]/1000)/(mass+ballast)
coupon_x_moment=sum(c['mass_kg']*p['coupon_axis_start_mm'][c['id']][0]/1000 for c in coupon_masses)
estimated_cg_x=coupon_x_moment/(mass+ballast)
result={'status':'design_calculation_only_not_physical_validation','mass_estimate_kg':mass,'frame_estimate_kg':frame_mass,
        'mass_with_3kg_ballast_estimate_kg':mass+ballast,
        'estimated_y_cg_without_ballast_m':y_moment/mass,'estimated_y_cg_with_ballast_m':cg_with_ballast,
        'estimated_x_cg_with_ballast_m':estimated_cg_x,'estimated_planar_cg_with_ballast_m':(estimated_cg_x**2+cg_with_ballast**2)**.5,
        'coupon_arm_3kg_design_load':{'force_N':arm_force,'tip_deflection_m':arm_deflection,'root_bending_stress_Pa':arm_force*.15*(brace_outer/2)/small_inertia,'lateral_eccentricity_m':.05,'torsion_Nm':arm_torque,'twist_rad':arm_twist,'coupon_edge_torsion_displacement_m':coupon_edge_displacement,'conservative_bending_plus_torsion_displacement_m':arm_deflection+coupon_edge_displacement,'poisson_ratio_assumption':poisson_ratio,'connection_slip_excluded':True},
        'coupon_masses':coupon_masses,'profile_area_m2':area,'profile_second_moment_m4':inertia,
        'wind_at_declared_limit':wind(a['calibration_wind_limit_m_s']),'wind_outside_declared_limit':wind(8),
        'thermal_scale_change_m':a['aluminum_alpha_per_K']*.65*a['temperature_difference_limit_K'],
        'assumptions':a,'cad_executed':False,
        'limitations':['Nominal sharp-corner sections, specified densities and ideal cantilever supports.',
                       'No bolt slip, soil settlement, real dynamic gust or physical specimen calibration data.',
                       'Mass, center of gravity, projected area and reference coordinates require physical confirmation.']}
assert result['wind_at_declared_limit']['overturning_requirement_met']
assert result['wind_at_declared_limit']['deflection_requirement_met']
assert not result['wind_outside_declared_limit']['overturning_requirement_met']
assert arm_deflection<=a['maximum_support_tip_deflection_m']
assert arm_deflection+coupon_edge_displacement<=a['maximum_support_tip_deflection_m']
assert result['estimated_planar_cg_with_ballast_m']<=a['center_of_gravity_offset_limit_m']
targets=p['reference_target_nominal_centers_mm']
import numpy as np
assert abs(float(np.linalg.det(np.asarray(targets[1:],float)-np.asarray(targets[0],float))))>0
out=PACKAGE/'mechanical/calculations.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('status','mass_estimate_kg','wind_at_declared_limit','wind_outside_declared_limit','thermal_scale_change_m')},ensure_ascii=False,indent=2))
