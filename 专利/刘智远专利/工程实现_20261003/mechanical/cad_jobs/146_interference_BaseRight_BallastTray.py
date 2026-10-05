import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('BallastTray')
print('BaseRight','BallastTray',a.Shape.common(b.Shape).Volume)
