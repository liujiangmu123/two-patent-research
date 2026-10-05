import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('C08')
print('BaseRear','C08',a.Shape.common(b.Shape).Volume)
