import FreeCAD as App
import TechDrawGui
from pathlib import Path
doc=App.getDocument('CheBlockDrawingV2')
path=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/05_工程图/阀块_V2_三视图.svg')
TechDrawGui.exportPageAsSvg(doc.Page,str(path))
_result_={'export':str(path),'exists':path.is_file(),'bytes':path.stat().st_size if path.is_file() else 0,'dimensions':[(o.Name,str(o.Measurement)) for o in doc.Objects if 'Measurement' in o.PropertiesList]}
