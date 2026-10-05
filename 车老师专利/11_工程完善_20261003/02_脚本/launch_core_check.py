import FreeCAD as App
import Part
import time
import threading
import traceback
job={'stage':'core_interference','status':'running','started':time.time()}
App._che_job=job
parts=[dict(p,shape=p['shape'].copy()) for p in App._che_core_parts]
def work():
    try:
        collisions=[];tested=0
        for i,a in enumerate(parts):
            job['detail']='checking '+a['no']+' '+str(i+1)+'/'+str(len(parts))
            for b in parts[i+1:]:
                if a['shape'].BoundBox.intersect(b['shape'].BoundBox):
                    tested+=1
                    volume=a['shape'].common(b['shape']).Volume
                    if volume>1e-4:
                        collisions.append({'a':a['no'],'b':b['no'],'volume_mm3':round(volume,6)})
        poses=[]
        moving=[p for p in parts if p['moving']]
        stationary=[p for p in parts if not p['moving'] and p['group']=='Cylinder']
        for stroke in (0,35,70,105,140):
            hits=[]
            for a in moving:
                s=a['shape'].copy();s.translate(App.Vector(70-stroke,0,0))
                for b in stationary:
                    if s.BoundBox.intersect(b['shape'].BoundBox):
                        volume=s.common(b['shape']).Volume
                        if volume>1e-4:hits.append({'a':a['no'],'b':b['no'],'volume_mm3':round(volume,6)})
            poses.append({'extension_mm':stroke,'collisions':hits})
        job.update(status='done',pair_count=tested,collisions=collisions,poses=poses,elapsed_s=round(time.time()-job['started'],2))
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
