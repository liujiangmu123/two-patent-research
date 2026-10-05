import FreeCAD as App
import importlib.util
import threading
import traceback
import time
path='H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/02_脚本/fine_core.py'
spec=importlib.util.spec_from_file_location('che_fine_core',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
job={'stage':'fine_core','status':'running','started':time.time()}
App._che_job=job
def work():
    try:
        parts,nets,summary=module.build(App._che_vendor,job)
        App._che_core_module=module
        App._che_core_parts=parts
        App._che_core_nets=nets
        App._che_core_summary=summary
        job.update(status='done',part_count=len(parts),summary=summary,elapsed_s=round(time.time()-job['started'],2))
    except Exception:
        job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'stage':'fine_core','status':'started'}
