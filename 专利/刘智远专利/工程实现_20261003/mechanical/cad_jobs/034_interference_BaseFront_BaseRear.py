import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('BaseRear')
print('BaseFront','BaseRear',a.Shape.common(b.Shape).Volume)
