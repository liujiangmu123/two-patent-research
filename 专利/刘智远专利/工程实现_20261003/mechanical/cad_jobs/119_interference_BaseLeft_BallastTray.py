import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('BallastTray')
print('BaseLeft','BallastTray',a.Shape.common(b.Shape).Volume)
