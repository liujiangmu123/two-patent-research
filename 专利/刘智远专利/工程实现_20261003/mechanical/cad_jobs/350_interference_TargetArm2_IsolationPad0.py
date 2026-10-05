import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('TargetArm2'); b=doc.getObject('IsolationPad0')
print('TargetArm2','IsolationPad0',a.Shape.common(b.Shape).Volume)
