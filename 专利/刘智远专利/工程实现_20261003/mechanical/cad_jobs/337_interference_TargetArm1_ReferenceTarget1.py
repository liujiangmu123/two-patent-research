import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('ReferenceTarget1')
print('TargetArm1','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
