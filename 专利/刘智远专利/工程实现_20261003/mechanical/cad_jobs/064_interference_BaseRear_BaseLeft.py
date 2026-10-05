import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('BaseLeft')
print('BaseRear','BaseLeft',a.Shape.common(b.Shape).Volume)
