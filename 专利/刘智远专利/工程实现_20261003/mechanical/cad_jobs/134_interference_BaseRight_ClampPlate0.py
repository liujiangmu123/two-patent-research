import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('ClampPlate0')
print('BaseRight','ClampPlate0',a.Shape.common(b.Shape).Volume)
