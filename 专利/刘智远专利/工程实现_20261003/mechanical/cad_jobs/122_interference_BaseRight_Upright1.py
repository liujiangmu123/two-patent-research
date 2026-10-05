import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('Upright1')
print('BaseRight','Upright1',a.Shape.common(b.Shape).Volume)
