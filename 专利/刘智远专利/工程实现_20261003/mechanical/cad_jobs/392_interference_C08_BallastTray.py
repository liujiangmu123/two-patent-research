import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C08'); b=doc.getObject('BallastTray')
print('C08','BallastTray',a.Shape.common(b.Shape).Volume)
