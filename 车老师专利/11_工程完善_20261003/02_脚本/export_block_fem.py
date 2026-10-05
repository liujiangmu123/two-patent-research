import FreeCAD as App
import json
from pathlib import Path
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/06_仿真/FEM')
root.mkdir(exist_ok=True)
block=next(p['shape'] for p in App._che_core_parts if p['no']=='BL-01')
block.exportBrep(str(root/'block.brep'))
# Surface properties and source geometry are preserved for mesh/load association checks.
faces=[]
for i,f in enumerate(block.Faces,1):
    c=f.CenterOfMass;b=f.BoundBox
    faces.append({'face':i,'area_mm2':f.Area,'center':list(c),'bbox':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax],'surface':type(f.Surface).__name__})
(root/'block_faces.json').write_text(json.dumps(faces,indent=2),encoding='utf-8')
_result_={'brep':str(root/'block.brep'),'faces':len(faces),'volume_mm3':block.Volume}
