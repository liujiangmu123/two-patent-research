import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget0'); b=doc.getObject('ReferenceTarget1')
print('ReferenceTarget0','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
