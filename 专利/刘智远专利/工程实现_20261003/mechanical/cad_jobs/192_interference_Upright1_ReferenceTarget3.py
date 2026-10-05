import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('ReferenceTarget3')
print('Upright1','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
