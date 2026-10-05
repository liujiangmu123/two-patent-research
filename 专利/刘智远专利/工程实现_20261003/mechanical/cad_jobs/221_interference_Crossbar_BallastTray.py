import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('BallastTray')
print('Crossbar','BallastTray',a.Shape.common(b.Shape).Volume)
