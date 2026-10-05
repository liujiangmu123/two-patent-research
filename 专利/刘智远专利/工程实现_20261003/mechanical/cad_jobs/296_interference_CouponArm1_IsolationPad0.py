import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('CouponArm1'); b=doc.getObject('IsolationPad0')
print('CouponArm1','IsolationPad0',a.Shape.common(b.Shape).Volume)
