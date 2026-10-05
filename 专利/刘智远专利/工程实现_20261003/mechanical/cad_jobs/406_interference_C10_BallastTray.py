import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('BallastTray')
print('C10','BallastTray',a.Shape.common(b.Shape).Volume)
