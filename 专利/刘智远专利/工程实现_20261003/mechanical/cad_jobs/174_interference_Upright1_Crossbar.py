import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Upright1'); b=doc.getObject('Crossbar')
print('Upright1','Crossbar',a.Shape.common(b.Shape).Volume)
