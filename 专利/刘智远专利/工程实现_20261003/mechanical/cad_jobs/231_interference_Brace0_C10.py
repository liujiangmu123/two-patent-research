import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace0'); b=doc.getObject('C10')
print('Brace0','C10',a.Shape.common(b.Shape).Volume)
