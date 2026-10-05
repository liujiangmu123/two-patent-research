import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('IsolationPad0')
print('BaseRear','IsolationPad0',a.Shape.common(b.Shape).Volume)
