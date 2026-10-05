import FreeCAD as App
import Part
import threading
import traceback
from pathlib import Path

ROOT = Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003')
job = {'stage': 'inspect_vendor', 'status': 'running'}
App._che_job = job

def work():
    try:
        shapes = {}
        summary = {}
        for name in ('SDSPM22-X5-BA.STEP', 'VDE37_19x50.STEP', 'HB0.STEP'):
            shape = Part.read(str(ROOT / '01_厂家依据/Wandfluh/STEP' / name))
            shapes[name] = shape
            bb = shape.BoundBox
            axes = []
            for f in shape.Faces:
                if isinstance(f.Surface, Part.Cylinder):
                    axes.append({'radius': round(f.Surface.Radius, 4),
                                 'center': list(f.Surface.Center), 'axis': list(f.Surface.Axis)})
            summary[name] = {'solids': len(shape.Solids), 'valid': shape.isValid(),
                             'bbox': [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax],
                             'cylinders': axes[:20]}
        App._che_vendor = shapes
        job.update(status='done', summary=summary)
    except Exception:
        job.update(status='failed', error=traceback.format_exc())

threading.Thread(target=work, daemon=True).start()
_result_ = {'stage': job['stage'], 'status': 'started'}
