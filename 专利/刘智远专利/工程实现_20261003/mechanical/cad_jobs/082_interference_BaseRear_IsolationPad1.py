import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('IsolationPad1')
print('BaseRear','IsolationPad1',a.Shape.common(b.Shape).Volume)
