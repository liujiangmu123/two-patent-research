import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('ClampPlate1')
print('BaseLeft','ClampPlate1',a.Shape.common(b.Shape).Volume)
