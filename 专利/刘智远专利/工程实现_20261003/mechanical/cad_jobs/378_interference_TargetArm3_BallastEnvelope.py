import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm3'); b=doc.getObject('BallastEnvelope')
print('TargetArm3','BallastEnvelope',a.Shape.common(b.Shape).Volume)
