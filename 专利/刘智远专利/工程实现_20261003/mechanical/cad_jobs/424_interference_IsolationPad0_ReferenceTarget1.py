import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad0'); b=doc.getObject('ReferenceTarget1')
print('IsolationPad0','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
