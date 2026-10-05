import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('ClampPlate1')
print('TargetArm1','ClampPlate1',a.Shape.common(b.Shape).Volume)
