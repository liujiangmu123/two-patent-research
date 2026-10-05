import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('车老师专利/11_工程完善_20261003/06_仿真/FEM').resolve()
coarse=json.loads((root/'block_coarse_results.json').read_text(encoding='utf-8'))
medium=json.loads((root/'block_medium_results.json').read_text(encoding='utf-8'))
delta={key:100*(medium[key]/coarse[key]-1) for key in ('max_von_mises_MPa','max_displacement_mm','stress_p99_MPa','stress_p999_MPa')}
report={'completed_cases':['block_coarse','block_medium'],'failed_case':'block_fine','failed_reason':'native0xC0000005 access violation,80-byte FRD has no valid fields','changes_percent_relative_coarse':delta,'interpretation':'overall displacement differs about1%; local peak rises about9.9% and is not sufficiently established as mesh-converged','provisional_review_criteria':{'displacement_change_percent':2,'peak_stress_change_percent':5,'status':'engineering screening assumptions, not a normative acceptance specification'},'peak_stress_converged':abs(delta['max_von_mises_MPa'])<5,'full_assembly_strength_verified':False,'boundary':'local nominal block only;7MPa uniformly on classified hole surfaces, whole bottom fixedXYZ, no valve/plug preload, contact or thread helix','current_model_geometry':'BL-01 from coreV2 including independentR-temperature bore; unchanged during chuckV3 refinement','coarse':coarse,'medium':medium}
(root/'网格比较与适用范围.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for data in (coarse,medium):
    data['mesh_convergence']='two completed meshes: displacement+1.025%, local peak+9.905%; peak not sufficiently converged; finest solver crashed'
    (root/(data['case']+'_results.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
fig,axes=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
keys=('max_von_mises_MPa','max_displacement_mm','stress_p999_MPa')
labels=('Peak von Mises / MPa','Maximum displacement / mm','99.9th percentile stress / MPa')
for ax,key,label in zip(axes,keys,labels):
    values=[coarse[key],medium[key]]
    bars=ax.bar(['Coarse','Medium'],values,color=['#527a9b','#be863c'])
    ax.set_ylabel(label);ax.set_ylim(0,max(values)*1.24)
    ax.bar_label(bars,labels=[f'{v:.6g}' for v in values],padding=4)
    ax.spines[['top','right']].set_visible(False)
fig.suptitle('Actual CalculiX results: local 7 MPa block case / peak convergence remains open',fontsize=11)
fig.savefig(root/'网格比较.png',dpi=180)
plt.close(fig)
print(json.dumps({'changes_percent':delta,'peak_converged':report['peak_stress_converged']},ensure_ascii=False))
