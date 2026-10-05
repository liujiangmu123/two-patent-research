import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm2'); b=doc.getObject('ReferenceTarget2')
print('TargetArm2','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
