import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('TargetArm1')
print('Brace0','TargetArm1',a.Shape.common(b.Shape).Volume)
