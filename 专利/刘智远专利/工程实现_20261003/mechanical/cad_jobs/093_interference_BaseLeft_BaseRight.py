import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('BaseRight')
print('BaseLeft','BaseRight',a.Shape.common(b.Shape).Volume)
