import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace1'); b=doc.getObject('C10')
print('Brace1','C10',a.Shape.common(b.Shape).Volume)
