import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('FootEnvelope1'); b=doc.getObject('BallastTray')
print('FootEnvelope1','BallastTray',a.Shape.common(b.Shape).Volume)
