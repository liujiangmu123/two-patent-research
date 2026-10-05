import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad0'); b=doc.getObject('ReferenceTarget0')
print('IsolationPad0','ReferenceTarget0',a.Shape.common(b.Shape).Volume)
