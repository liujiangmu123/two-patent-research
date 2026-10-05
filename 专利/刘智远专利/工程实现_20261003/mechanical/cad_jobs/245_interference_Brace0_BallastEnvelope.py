import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('BallastEnvelope')
print('Brace0','BallastEnvelope',a.Shape.common(b.Shape).Volume)
