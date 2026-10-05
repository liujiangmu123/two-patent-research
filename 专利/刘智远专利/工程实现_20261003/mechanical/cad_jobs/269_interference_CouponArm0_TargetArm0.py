import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm0'); b=doc.getObject('TargetArm0')
print('CouponArm0','TargetArm0',a.Shape.common(b.Shape).Volume)
