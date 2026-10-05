"""File-based delivery evidence; no CAD execution or original-file modification."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
root=Path('车老师专利/11_工程完善_20261003').resolve()
out=root/'07_交付'
out.mkdir(exist_ok=True)
fields=['no','name','group','material','basis','thread','notes','moving','valid','solids','volume_mm3']
counts={}
for label,source in [('尾座总成',root/'04_检查/精细核心零件清单.json'),('试验台',root/'04_检查/精细试验台零件清单.json')]:
    data=json.loads(source.read_text(encoding='utf-8'))
    parts=data['parts'];counts[label]=len(parts)
    with (out/(label+'_BOM.csv')).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(parts)
files=[]
for directory in ('00_设计基准','03_模型','04_检查','05_工程图'):
    for p in (root/directory).rglob('*'):
        if p.is_file() and p.suffix.lower() not in ('.fcstd1','.bak'):
            files.append({'file':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
index={'updated_at':datetime.datetime.now().astimezone().isoformat(),'status':'engineering work in progress, not released for manufacture or patent filing','part_counts':counts,'latest_models':{'core':'03_模型/精细尾座阀块油缸_V2.FCStd','bench':'03_模型/精细液压试验台_V3.FCStd','historical_benchV2':'389-part saved prior snapshot; current BOM is for V3'},'blender':'supplied E folder contains only addon_blendermcp.py; no executable in folder; no live Blender connection','verification':'tailstock140mm and standalone chuck20mm each checked in5 positions; final bench nominal intersections checked;16 vendor-internal intersections retained','simulation':'CalculiX local block7MPa coarse and medium cases completed; finest case failed with0xC0000005; peak stress changes9.905% and is not sufficiently converged','open_items':['complete hydraulic hose/valveboard/thermal service connections and every fixture fastening','all-part manufacturing dimensions, drilling access, tolerance and seal closure review','full force chain static/fatigue/contact FEA, thermal and dynamic modelling','P1-P3 qualified algorithms and fault/tolerance simulations','licensed FluidSIM and AMESim runs;3D flow simulation not executed','Blender executable location and live addon connection','patent descriptions/claims/figures consistency updates and additional prior-art search','procurement interface confirmation, physical manufacture, hydrostatic/leak/thermal/force tests'],'files':files}
(out/'交付文件索引.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'BOM_counts':counts,'indexed_files':len(files)},ensure_ascii=False))
