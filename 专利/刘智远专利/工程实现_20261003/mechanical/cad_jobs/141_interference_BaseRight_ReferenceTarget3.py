import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('ReferenceTarget3')
print('BaseRight','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
