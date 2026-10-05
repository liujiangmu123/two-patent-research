import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm0'); b=doc.getObject('ReferenceTarget2')
print('CouponArm0','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
