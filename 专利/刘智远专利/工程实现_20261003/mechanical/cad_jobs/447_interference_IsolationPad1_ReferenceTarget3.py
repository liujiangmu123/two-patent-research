import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad1'); b=doc.getObject('ReferenceTarget3')
print('IsolationPad1','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
