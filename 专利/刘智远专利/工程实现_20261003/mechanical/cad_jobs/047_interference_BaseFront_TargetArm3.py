import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('TargetArm3')
print('BaseFront','TargetArm3',a.Shape.common(b.Shape).Volume)
