import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('ReferenceTarget1')
print('Crossbar','ReferenceTarget1',a.Shape.common(b.Shape).Volume)
