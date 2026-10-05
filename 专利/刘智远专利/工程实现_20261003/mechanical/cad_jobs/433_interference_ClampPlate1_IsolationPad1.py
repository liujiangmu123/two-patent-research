import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate1'); b=doc.getObject('IsolationPad1')
print('ClampPlate1','IsolationPad1',a.Shape.common(b.Shape).Volume)
