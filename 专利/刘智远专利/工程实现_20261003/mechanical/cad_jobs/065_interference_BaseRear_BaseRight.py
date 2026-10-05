import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRear'); b=doc.getObject('BaseRight')
print('BaseRear','BaseRight',a.Shape.common(b.Shape).Volume)
