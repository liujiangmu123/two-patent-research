import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright0'); b=doc.getObject('TargetArm0')
print('Upright0','TargetArm0',a.Shape.common(b.Shape).Volume)
