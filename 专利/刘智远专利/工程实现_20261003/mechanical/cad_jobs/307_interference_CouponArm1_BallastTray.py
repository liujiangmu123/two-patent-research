import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('BallastTray')
print('CouponArm1','BallastTray',a.Shape.common(b.Shape).Volume)
