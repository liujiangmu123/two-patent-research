import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('BaseRight')
print('BaseFront','BaseRight',a.Shape.common(b.Shape).Volume)
