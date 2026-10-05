import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('IsolationPad0')
print('Crossbar','IsolationPad0',a.Shape.common(b.Shape).Volume)
