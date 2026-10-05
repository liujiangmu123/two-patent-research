import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('Brace1')
print('Upright1','Brace1',a.Shape.common(b.Shape).Volume)
