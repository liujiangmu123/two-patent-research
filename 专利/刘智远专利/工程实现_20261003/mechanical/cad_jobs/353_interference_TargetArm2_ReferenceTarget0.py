import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm2'); b=doc.getObject('ReferenceTarget0')
print('TargetArm2','ReferenceTarget0',a.Shape.common(b.Shape).Volume)
