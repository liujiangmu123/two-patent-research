import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget3'); b=doc.getObject('BallastEnvelope')
print('ReferenceTarget3','BallastEnvelope',a.Shape.common(b.Shape).Volume)
