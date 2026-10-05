import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('FootEnvelope3')
print('CouponArm1','FootEnvelope3',a.Shape.common(b.Shape).Volume)
