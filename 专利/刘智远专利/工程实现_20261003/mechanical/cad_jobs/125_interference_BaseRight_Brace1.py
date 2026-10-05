import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('Brace1')
print('BaseRight','Brace1',a.Shape.common(b.Shape).Volume)
