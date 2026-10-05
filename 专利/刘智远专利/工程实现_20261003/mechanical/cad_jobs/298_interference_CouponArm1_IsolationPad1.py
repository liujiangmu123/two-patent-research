import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('IsolationPad1')
print('CouponArm1','IsolationPad1',a.Shape.common(b.Shape).Volume)
