import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace1'); b=doc.getObject('IsolationPad1')
print('Brace1','IsolationPad1',a.Shape.common(b.Shape).Volume)
