import json
from pathlib import Path
root=Path('车老师专利/11_工程完善_20261003/00_设计基准')
path=root/'统一设计基准.json'
data=json.loads(path.read_text(encoding='utf-8'))
data['mechanical_revision']={'cylinder_tie_rods':{'size':'4xM10','yz_centres':[[8,-8],[8,-82],[82,-8],[82,-82]]},'block_bolts_xy':[[10,25],[10,65],[242,25],[242,65]],'block_dowels_xy':[[28,20],[222,70]],'cylinder_mount_xy':[[10,18],[10,72],[242,18],[242,72]],'piston_nut':'recessed M24x1.5, 140mm exact stop stroke','M22_cavity_source':'Wandfluh3-395.4,2.13-1008,2026 edition26 36','M22_bottom':'180 degree permitted drill bottom; 41.5mm pilot depth','orifice_z':[16,20],'orifice_diameter':.1,'second_relief':'independent C chamber, nominal M20, rear x199,z21','dual_temperature':'C originalM14 well; R addedM10x1 well x99,z14','bench_core_translation':[1365,455,1125],'bench_bed_length':1470,'guard_left_x':100,'wedge_needles':'28 per surface, nominal3x30 mm'}
data['measurement_requirements']={'pressure':'0..10MPa, candidate accuracy0.05%FS; final order code pending','temperature':'two independent cavityPt100 channels; compensate measured lag, identify on bench','force_reference':'20kN load cell, assumed0.1%FS; reference feedback and friction calibration on test bench','displacement_reference':'LVDT +-1mm, target0.5um; physical calibration pending'}
data['hydraulic_leakage']={'Wandfluh_SDSPM22_spec_max_mLmin':.15,'reference_viscosity_cSt':30,'assumption':'published maximum is not zero; sweep leakage in simulation; actual set measured before finalising hold/reconstruction claims'}
data['software_limits']={'FluidSIM':'not found on current machine','AMESim':'original.ame files preserved; solver/license not found','Blender':'MCP installed, Blender application/addon connection not yet available'}
path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Design revision registered')
