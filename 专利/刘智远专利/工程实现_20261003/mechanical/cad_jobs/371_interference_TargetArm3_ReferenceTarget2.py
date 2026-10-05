import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('ReferenceTarget2')
print('TargetArm3','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
