import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('C10')
print('TargetArm3','C10',a.Shape.common(b.Shape).Volume)
