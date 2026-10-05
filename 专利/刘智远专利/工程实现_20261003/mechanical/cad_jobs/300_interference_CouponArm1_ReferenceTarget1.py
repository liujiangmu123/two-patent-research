import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('ReferenceTarget1')
print('CouponArm1','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
