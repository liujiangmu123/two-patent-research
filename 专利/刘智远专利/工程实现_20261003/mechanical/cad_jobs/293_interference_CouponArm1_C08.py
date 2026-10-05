import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('C08')
print('CouponArm1','C08',a.Shape.common(b.Shape).Volume)
