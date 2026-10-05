import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright0'); b=doc.getObject('Upright1')
print('Upright0','Upright1',a.Shape.common(b.Shape).Volume)
