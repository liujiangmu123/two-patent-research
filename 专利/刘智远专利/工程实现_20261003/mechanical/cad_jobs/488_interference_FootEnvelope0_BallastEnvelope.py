import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('FootEnvelope0'); b=doc.getObject('BallastEnvelope')
print('FootEnvelope0','BallastEnvelope',a.Shape.common(b.Shape).Volume)
