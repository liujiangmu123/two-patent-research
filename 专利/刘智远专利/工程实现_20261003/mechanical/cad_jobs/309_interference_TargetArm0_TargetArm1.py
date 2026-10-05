import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm0'); b=doc.getObject('TargetArm1')
print('TargetArm0','TargetArm1',a.Shape.common(b.Shape).Volume)
