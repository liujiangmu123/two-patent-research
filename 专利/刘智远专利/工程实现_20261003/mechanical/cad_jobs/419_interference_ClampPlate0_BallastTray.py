import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('BallastTray')
print('ClampPlate0','BallastTray',a.Shape.common(b.Shape).Volume)
