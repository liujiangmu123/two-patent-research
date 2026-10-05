import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('ClampPlate1')
print('C10','ClampPlate1',a.Shape.common(b.Shape).Volume)
