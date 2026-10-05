import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('ClampPlate0')
print('C10','ClampPlate0',a.Shape.common(b.Shape).Volume)
