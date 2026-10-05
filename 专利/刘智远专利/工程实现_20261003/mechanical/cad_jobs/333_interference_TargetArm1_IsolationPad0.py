import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm1'); b=doc.getObject('IsolationPad0')
print('TargetArm1','IsolationPad0',a.Shape.common(b.Shape).Volume)
