import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright0'); b=doc.getObject('Brace1')
print('Upright0','Brace1',a.Shape.common(b.Shape).Volume)
