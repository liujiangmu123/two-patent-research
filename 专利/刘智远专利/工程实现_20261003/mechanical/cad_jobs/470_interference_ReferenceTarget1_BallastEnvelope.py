import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget1'); b=doc.getObject('BallastEnvelope')
print('ReferenceTarget1','BallastEnvelope',a.Shape.common(b.Shape).Volume)
