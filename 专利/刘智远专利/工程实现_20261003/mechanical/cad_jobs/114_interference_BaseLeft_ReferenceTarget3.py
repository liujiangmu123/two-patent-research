import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('ReferenceTarget3')
print('BaseLeft','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
