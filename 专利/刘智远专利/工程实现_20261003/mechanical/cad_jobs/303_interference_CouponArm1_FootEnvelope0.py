import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('FootEnvelope0')
print('CouponArm1','FootEnvelope0',a.Shape.common(b.Shape).Volume)
