import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm0'); b=doc.getObject('ClampPlate1')
print('CouponArm0','ClampPlate1',a.Shape.common(b.Shape).Volume)
