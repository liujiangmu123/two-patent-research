import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('IsolationPad0')
print('ClampPlate0','IsolationPad0',a.Shape.common(b.Shape).Volume)
