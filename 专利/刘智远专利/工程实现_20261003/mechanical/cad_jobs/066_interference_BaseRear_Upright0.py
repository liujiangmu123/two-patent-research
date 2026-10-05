import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('Upright0')
print('BaseRear','Upright0',a.Shape.common(b.Shape).Volume)
