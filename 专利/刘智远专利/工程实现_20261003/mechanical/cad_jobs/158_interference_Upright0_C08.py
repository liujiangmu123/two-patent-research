import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright0'); b=doc.getObject('C08')
print('Upright0','C08',a.Shape.common(b.Shape).Volume)
