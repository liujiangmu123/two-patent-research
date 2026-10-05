import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('ClampPlate1')
print('Crossbar','ClampPlate1',a.Shape.common(b.Shape).Volume)
