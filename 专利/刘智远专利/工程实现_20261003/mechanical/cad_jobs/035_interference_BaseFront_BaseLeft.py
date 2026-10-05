import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('BaseLeft')
print('BaseFront','BaseLeft',a.Shape.common(b.Shape).Volume)
