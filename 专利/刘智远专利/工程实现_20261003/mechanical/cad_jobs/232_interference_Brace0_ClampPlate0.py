import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('ClampPlate0')
print('Brace0','ClampPlate0',a.Shape.common(b.Shape).Volume)
