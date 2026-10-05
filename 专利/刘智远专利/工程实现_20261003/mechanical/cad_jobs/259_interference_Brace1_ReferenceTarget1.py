import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace1'); b=doc.getObject('ReferenceTarget1')
print('Brace1','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
