import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BallastTray'); b=doc.getObject('BallastEnvelope')
print('BallastTray','BallastEnvelope',a.Shape.common(b.Shape).Volume)
