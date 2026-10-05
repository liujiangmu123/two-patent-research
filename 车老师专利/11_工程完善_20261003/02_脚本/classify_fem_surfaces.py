import FreeCAD as App
import Part
import json
import threading
import traceback
from pathlib import Path
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/06_仿真/FEM')
name='block_coarse'
samples=json.loads((root/(name+'_samples.json')).read_text())
job={'stage':'fem_surface_selection','status':'running'};App._che_job=job
hydro=[s.copy() for k,s in App._che_core_nets.items() if not k.startswith(('Z_','Cylinder')) and '密封槽' not in k]
def work():
    try:
        wet=[];votes={}
        for tag,pts in samples.items():
            hits=0
            for xyz in pts:
                p=App.Vector(*xyz)
                if any(s.BoundBox.isInside(p) and s.isInside(p,1e-6,True) for s in hydro):hits+=1
            votes[tag]={'inside':hits,'sampled':len(pts)}
            if hits/len(pts)>=.75:wet.append(int(tag))
        result={'wet_surfaces':wet,'votes':votes,'assumption':'uniform pressure on nominal hydraulic-hole surfaces; commercial valve internals excluded'}
        (root/(name+'_wet_surfaces.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        job.update(status='done',selected_count=len(wet),surface_count=len(samples))
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
