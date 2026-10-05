import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('ClampPlate1')
print('TargetArm3','ClampPlate1',a.Shape.common(b.Shape).Volume)
