import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('Crossbar')
print('BaseRight','Crossbar',a.Shape.common(b.Shape).Volume)
