import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('ReferenceTarget3')
print('TargetArm1','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
