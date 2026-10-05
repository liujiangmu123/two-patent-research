import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('ReferenceTarget0')
print('BaseLeft','ReferenceTarget0',a.Shape.common(b.Shape).Volume)
