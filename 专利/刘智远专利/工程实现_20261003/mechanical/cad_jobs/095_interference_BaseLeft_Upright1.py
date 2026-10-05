import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('Upright1')
print('BaseLeft','Upright1',a.Shape.common(b.Shape).Volume)
