import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget1'); b=doc.getObject('ReferenceTarget3')
print('ReferenceTarget1','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
