import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('C08')
print('TargetArm3','C08',a.Shape.common(b.Shape).Volume)
