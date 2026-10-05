import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('ReferenceTarget1')
print('BaseRear','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
