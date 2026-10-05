import FreeCAD as App
from PySide import QtCore,QtGui,QtSvg
from pathlib import Path
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003/05_工程图')
renderer=QtSvg.QSvgRenderer(str(root/'阀块_V2_三视图.svg'))
assert renderer.isValid(),'SVG renderer rejected export'
image=QtGui.QImage(2000,1414,QtGui.QImage.Format_ARGB32)
image.fill(QtGui.QColor('white'))
painter=QtGui.QPainter(image)
renderer.render(painter)
painter.end()
path=root/'阀块_V2_三视图.png'
assert image.save(str(path))
doc=App.getDocument('CheBlockDrawingV2')
dim=[]
for o in doc.Objects:
    if o.TypeId=='TechDraw::DrawViewDimension':
        dim.append({'name':o.Name,'state':o.State,'properties':o.PropertiesList,'methods':[n for n in dir(o) if 'Value' in n or 'Measure' in n]})
_result_={'image':str(path),'dimensions':dim}
