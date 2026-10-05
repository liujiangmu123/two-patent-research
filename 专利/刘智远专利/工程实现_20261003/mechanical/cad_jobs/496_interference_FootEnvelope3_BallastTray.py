import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('FootEnvelope3'); b=doc.getObject('BallastTray')
print('FootEnvelope3','BallastTray',a.Shape.common(b.Shape).Volume)
