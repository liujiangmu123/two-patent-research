import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('ReferenceTarget2')
print('BaseFront','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
