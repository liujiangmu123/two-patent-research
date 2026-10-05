import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm0'); b=doc.getObject('BallastEnvelope')
print('CouponArm0','BallastEnvelope',a.Shape.common(b.Shape).Volume)
