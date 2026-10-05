import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('ClampPlate0')
print('TargetArm3','ClampPlate0',a.Shape.common(b.Shape).Volume)
