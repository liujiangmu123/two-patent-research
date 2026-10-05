import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad1'); b=doc.getObject('ReferenceTarget2')
print('IsolationPad1','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
