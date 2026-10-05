import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('TargetArm3')
print('BaseLeft','TargetArm3',a.Shape.common(b.Shape).Volume)
