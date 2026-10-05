import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('IsolationPad1')
print('BaseLeft','IsolationPad1',a.Shape.common(b.Shape).Volume)
