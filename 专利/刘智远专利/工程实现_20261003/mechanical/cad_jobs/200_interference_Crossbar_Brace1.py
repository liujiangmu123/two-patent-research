import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('Brace1')
print('Crossbar','Brace1',a.Shape.common(b.Shape).Volume)
