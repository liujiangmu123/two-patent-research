import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('ClampPlate0')
print('BaseFront','ClampPlate0',a.Shape.common(b.Shape).Volume)
