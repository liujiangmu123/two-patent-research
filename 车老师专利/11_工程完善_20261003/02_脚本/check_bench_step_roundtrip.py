import FreeCAD as App
import Part
import threading
import traceback
import time
from pathlib import Path
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003')
expected=Part.makeCompound([p['shape'].copy() for p in App._che_bench_parts])
path=root/'03_模型/精细液压试验台_V2.step'
job={'stage':'bench_step_roundtrip','status':'running','started':time.time()};App._che_job=job
def work():
    try:
        shape=Part.read(str(path))
        error=abs(shape.Volume-expected.Volume)/expected.Volume
        job.update(status='done',valid=shape.isValid(),imported_solids=len(shape.Solids),expected_solids=len(expected.Solids),relative_volume_difference=error,box_mm=[shape.BoundBox.XLength,shape.BoundBox.YLength,shape.BoundBox.ZLength],expected_box_mm=[expected.BoundBox.XLength,expected.BoundBox.YLength,expected.BoundBox.ZLength],elapsed_s=round(time.time()-job['started'],2))
    except Exception:job.update(status='failed',error=traceback.format_exc())
threading.Thread(target=work,daemon=True).start()
_result_={'status':'started','stage':job['stage']}
