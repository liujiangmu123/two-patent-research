import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm0'); b=doc.getObject('FootEnvelope1')
print('TargetArm0','FootEnvelope1',a.Shape.common(b.Shape).Volume)
