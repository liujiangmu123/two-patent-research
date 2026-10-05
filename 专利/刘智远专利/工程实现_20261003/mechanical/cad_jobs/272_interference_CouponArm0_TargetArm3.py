import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm0'); b=doc.getObject('TargetArm3')
print('CouponArm0','TargetArm3',a.Shape.common(b.Shape).Volume)
