import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('Brace0')
print('BaseFront','Brace0',a.Shape.common(b.Shape).Volume)
