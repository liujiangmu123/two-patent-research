import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm2'); b=doc.getObject('BallastTray')
print('TargetArm2','BallastTray',a.Shape.common(b.Shape).Volume)
