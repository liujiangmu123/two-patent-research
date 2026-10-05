import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('IsolationPad1')
print('ClampPlate0','IsolationPad1',a.Shape.common(b.Shape).Volume)
