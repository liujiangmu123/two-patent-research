import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('TargetArm3')
print('Crossbar','TargetArm3',a.Shape.common(b.Shape).Volume)
