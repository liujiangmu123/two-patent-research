import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('TargetArm3')
print('TargetArm1','TargetArm3',a.Shape.common(b.Shape).Volume)
