import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('BallastTray')
print('Brace0','BallastTray',a.Shape.common(b.Shape).Volume)
