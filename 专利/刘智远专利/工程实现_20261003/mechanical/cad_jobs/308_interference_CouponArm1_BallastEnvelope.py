import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('BallastEnvelope')
print('CouponArm1','BallastEnvelope',a.Shape.common(b.Shape).Volume)
