import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget2'); b=doc.getObject('BallastEnvelope')
print('ReferenceTarget2','BallastEnvelope',a.Shape.common(b.Shape).Volume)
