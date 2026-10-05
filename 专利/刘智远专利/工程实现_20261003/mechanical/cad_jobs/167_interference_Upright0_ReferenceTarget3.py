import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright0'); b=doc.getObject('ReferenceTarget3')
print('Upright0','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
