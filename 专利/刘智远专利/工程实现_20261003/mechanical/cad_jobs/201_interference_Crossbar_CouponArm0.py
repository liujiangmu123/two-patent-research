import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('CouponArm0')
print('Crossbar','CouponArm0',a.Shape.common(b.Shape).Volume)
