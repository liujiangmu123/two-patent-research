import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('CouponArm1')
print('BaseRight','CouponArm1',a.Shape.common(b.Shape).Volume)
