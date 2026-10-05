import FreeCAD as App
import Part
import threading
import time
import traceback
from pathlib import Path
doc=App.getDocument('CheBenchV2')
objects=[o for o in doc.Objects if 'EngineeringPartNo' in o.PropertiesList]
path=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/03_模型/精细液压试验台_V3.step')
job={'stage':'bench_step_export','status':'running','started':time.time()};App._che_job=job
def work():
    try:
        Part.export(objects,str(path))
        job.update(status='done',file=str(path),parts=len(objects),bytes=path.stat().st_size,elapsed_s=round(time.time()-job['started'],2))
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
