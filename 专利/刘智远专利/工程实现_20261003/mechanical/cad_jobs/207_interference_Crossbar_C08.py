import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('C08')
print('Crossbar','C08',a.Shape.common(b.Shape).Volume)
