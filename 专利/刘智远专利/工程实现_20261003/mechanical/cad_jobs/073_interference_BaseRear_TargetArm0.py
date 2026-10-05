import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('TargetArm0')
print('BaseRear','TargetArm0',a.Shape.common(b.Shape).Volume)
