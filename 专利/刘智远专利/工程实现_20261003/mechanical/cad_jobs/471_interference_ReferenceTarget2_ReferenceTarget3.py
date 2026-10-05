import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget2'); b=doc.getObject('ReferenceTarget3')
print('ReferenceTarget2','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
