import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('TargetArm0')
print('BaseRight','TargetArm0',a.Shape.common(b.Shape).Volume)
