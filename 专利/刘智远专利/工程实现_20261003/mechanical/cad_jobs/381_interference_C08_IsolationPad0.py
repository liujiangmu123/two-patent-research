import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C08'); b=doc.getObject('IsolationPad0')
print('C08','IsolationPad0',a.Shape.common(b.Shape).Volume)
