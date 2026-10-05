import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('ReferenceTarget0')
print('Upright1','ReferenceTarget0',a.Shape.common(b.Shape).Volume)
