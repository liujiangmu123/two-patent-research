import sys
import json
import re
import hashlib
from pathlib import Path
import numpy as np
from mesh_io import read_mesh,ROOT
name=sys.argv[1]
nodes,_,_=read_mesh(ROOT/(name+'.msh'))
fields={};active=None
pattern=re.compile(r'[-+]?\d*\.\d+(?:[EeDd][-+]?\d+)?')
with (ROOT/(name+'.frd')).open(encoding='ascii') as stream:
    for line in stream:
        if line.startswith(' -4'):
            active=line.split()[1];fields[active]={}
        elif line.startswith(' -3'):active=None
        elif active and line.startswith(' -1'):
            n=int(line[3:13]);vals=[float(s.replace('D','E')) for s in pattern.findall(line[13:])]
            fields[active][n]=vals
stress=fields['STRESS'];ids=list(stress);s=np.array([stress[n][:6] for n in ids])
vm=np.sqrt(.5*((s[:,0]-s[:,1])**2+(s[:,1]-s[:,2])**2+(s[:,2]-s[:,0])**2)+3*np.sum(s[:,3:6]**2,axis=1))
disp=fields['DISP'];du=np.linalg.norm(np.array([v[:3] for v in disp.values()]),axis=1)
imax=int(np.argmax(vm));result={'case':name,'fields':list(fields),'max_von_mises_MPa':float(vm[imax]),'stress_p99_MPa':float(np.quantile(vm,.99)),'stress_p999_MPa':float(np.quantile(vm,.999)),'max_stress_node':ids[imax],'max_stress_position_mm':nodes[ids[imax]].tolist(),'max_displacement_mm':float(max(du)),'yield_lower_bound_MPa':355,'peak_yield_margin':float(355/max(vm)),'proof_10_5MPa_peak_linear_scaled_MPa':float(max(vm)*1.5),'assumptions':'nominal hole stress at7MPa, fixed bottom, elastic45steel, no valve preload/thread helix or assembly contacts','mesh_convergence':'pending second mesh; sharp corners may create nonconvergent local peaks','files':{}}
for ext in ('brep','msh','inp','frd','sta','dat'):
    path=ROOT/('block.brep' if ext=='brep' else name+'.'+ext)
    if path.exists():result['files'][path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(ROOT/(name+'_results.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
np.savez_compressed(ROOT/(name+'_nodal_fields.npz'),node_ids=ids,von_mises=vm,xyz=np.array([nodes[n] for n in ids]))
print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))
