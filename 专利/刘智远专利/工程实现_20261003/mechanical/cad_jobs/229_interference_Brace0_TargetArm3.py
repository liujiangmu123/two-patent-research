import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('TargetArm3')
print('Brace0','TargetArm3',a.Shape.common(b.Shape).Volume)
