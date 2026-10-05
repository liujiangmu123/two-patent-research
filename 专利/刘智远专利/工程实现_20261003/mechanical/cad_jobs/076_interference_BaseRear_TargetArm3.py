import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('TargetArm3')
print('BaseRear','TargetArm3',a.Shape.common(b.Shape).Volume)
