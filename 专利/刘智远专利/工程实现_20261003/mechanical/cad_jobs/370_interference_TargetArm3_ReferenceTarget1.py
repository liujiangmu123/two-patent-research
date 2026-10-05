import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('ReferenceTarget1')
print('TargetArm3','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
