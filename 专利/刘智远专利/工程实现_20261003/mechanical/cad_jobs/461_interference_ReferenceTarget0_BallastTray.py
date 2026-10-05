import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget0'); b=doc.getObject('BallastTray')
print('ReferenceTarget0','BallastTray',a.Shape.common(b.Shape).Volume)
