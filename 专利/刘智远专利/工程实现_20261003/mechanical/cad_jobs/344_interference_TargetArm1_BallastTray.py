import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('BallastTray')
print('TargetArm1','BallastTray',a.Shape.common(b.Shape).Volume)
