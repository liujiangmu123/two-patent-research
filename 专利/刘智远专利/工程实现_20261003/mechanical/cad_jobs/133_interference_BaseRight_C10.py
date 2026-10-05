import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('C10')
print('BaseRight','C10',a.Shape.common(b.Shape).Volume)
