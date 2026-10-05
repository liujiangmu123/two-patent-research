import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad0'); b=doc.getObject('ReferenceTarget2')
print('IsolationPad0','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
