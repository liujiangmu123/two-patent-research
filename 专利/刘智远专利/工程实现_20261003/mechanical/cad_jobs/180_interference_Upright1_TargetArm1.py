import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('TargetArm1')
print('Upright1','TargetArm1',a.Shape.common(b.Shape).Volume)
