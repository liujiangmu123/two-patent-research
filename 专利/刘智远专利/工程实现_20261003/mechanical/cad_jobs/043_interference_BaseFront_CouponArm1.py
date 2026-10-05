import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('CouponArm1')
print('BaseFront','CouponArm1',a.Shape.common(b.Shape).Volume)
