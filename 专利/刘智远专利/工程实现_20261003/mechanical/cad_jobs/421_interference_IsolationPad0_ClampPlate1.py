import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad0'); b=doc.getObject('ClampPlate1')
print('IsolationPad0','ClampPlate1',a.Shape.common(b.Shape).Volume)
