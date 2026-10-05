import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm0'); b=doc.getObject('C10')
print('TargetArm0','C10',a.Shape.common(b.Shape).Volume)
