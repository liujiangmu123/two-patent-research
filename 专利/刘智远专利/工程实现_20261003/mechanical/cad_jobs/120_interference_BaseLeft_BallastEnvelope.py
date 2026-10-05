import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('BallastEnvelope')
print('BaseLeft','BallastEnvelope',a.Shape.common(b.Shape).Volume)
