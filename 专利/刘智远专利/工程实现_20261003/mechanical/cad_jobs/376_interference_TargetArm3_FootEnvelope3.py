import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('FootEnvelope3')
print('TargetArm3','FootEnvelope3',a.Shape.common(b.Shape).Volume)
