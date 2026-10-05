import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('C08')
print('Upright1','C08',a.Shape.common(b.Shape).Volume)
