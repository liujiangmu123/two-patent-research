import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('FootEnvelope0')
print('Crossbar','FootEnvelope0',a.Shape.common(b.Shape).Volume)
