import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate1'); b=doc.getObject('BallastTray')
print('ClampPlate1','BallastTray',a.Shape.common(b.Shape).Volume)
