import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('ClampPlate1')
print('BaseRight','ClampPlate1',a.Shape.common(b.Shape).Volume)
