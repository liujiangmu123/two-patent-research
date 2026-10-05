import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('FootEnvelope1')
print('Crossbar','FootEnvelope1',a.Shape.common(b.Shape).Volume)
