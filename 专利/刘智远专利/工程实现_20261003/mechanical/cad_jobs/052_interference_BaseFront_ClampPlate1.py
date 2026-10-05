import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('ClampPlate1')
print('BaseFront','ClampPlate1',a.Shape.common(b.Shape).Volume)
