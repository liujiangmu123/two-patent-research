import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('CouponArm0')
print('BaseRight','CouponArm0',a.Shape.common(b.Shape).Volume)
