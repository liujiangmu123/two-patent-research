import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm2'); b=doc.getObject('FootEnvelope2')
print('TargetArm2','FootEnvelope2',a.Shape.common(b.Shape).Volume)
