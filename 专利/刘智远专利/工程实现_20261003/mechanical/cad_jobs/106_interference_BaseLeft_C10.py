import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('C10')
print('BaseLeft','C10',a.Shape.common(b.Shape).Volume)
