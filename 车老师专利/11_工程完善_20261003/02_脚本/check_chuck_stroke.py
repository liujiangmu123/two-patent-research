import FreeCAD as App
import threading
import traceback
import time
import json
from pathlib import Path
moving={'CH-PIS','CH-ROD','CH-PN','CH-GPA','CH-GPB','CH-SP','CH-EP'}
fixed={'CH-CYL','CH-CF','CH-CR','CH-GR','CH-SR1','CH-SR2','CH-SW','CH-PFC','CH-PFR'}
parts={p['no']:p['shape'].copy() for p in App._che_bench_parts if p['no'] in moving|fixed or p['no'].startswith('CH-SE-C')}
job={'stage':'chuck_stroke_check','status':'running','started':time.time()};App._che_job=job
def work():
    try:
        results=[]
        for extension in (0,5,10,15,20):
            hits=[]
            for no in moving:
                s=parts[no].copy();s.translate(App.Vector(extension-10,0,0))
                for fn in parts.keys()-moving:
                    q=parts[fn]
                    if s.BoundBox.intersect(q.BoundBox):
                        volume=s.common(q).Volume
                        if volume>1e-4:hits.append({'moving':no,'fixed':fn,'volume_mm3':volume})
            results.append({'extension_mm':extension,'collisions':hits})
        job.update(status='done',poses=results,scope='standalone nonrotating actuator internal travel; disc-spring deformation and chuck linkage are excluded',elapsed_s=round(time.time()-job['started'],2))
        path=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/04_检查/卡盘试验缸20mm行程检查.json')
        path.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
