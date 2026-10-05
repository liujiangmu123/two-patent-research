import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('Brace1')
print('BaseRear','Brace1',a.Shape.common(b.Shape).Volume)
