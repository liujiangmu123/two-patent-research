import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('ClampPlate0')
print('Upright1','ClampPlate0',a.Shape.common(b.Shape).Volume)
