import FreeCAD as App
import Part
import time
import threading
import traceback
job={'stage':'bench_interference','status':'running','started':time.time()};App._che_job=job
parts=[dict(p,shape=p['shape'].copy()) for p in App._che_bench_parts]
def work():
    try:
        collisions=[];tested=0
        for i,a in enumerate(parts):
            job['detail']=str(i+1)+'/'+str(len(parts))+' '+a['no']
            for b in parts[i+1:]:
                if a['shape'].BoundBox.intersect(b['shape'].BoundBox):
                    tested+=1
                    v=a['shape'].common(b['shape']).Volume
                    if v>1e-4:collisions.append({'a':a['no'],'b':b['no'],'volume_mm3':round(v,6)})
        job.update(status='done',pair_count=tested,collisions=collisions,elapsed_s=round(time.time()-job['started'],2))
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
