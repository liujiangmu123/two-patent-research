import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('ReferenceTarget1')
print('C10','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
