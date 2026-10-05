import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('FootEnvelope3')
print('Crossbar','FootEnvelope3',a.Shape.common(b.Shape).Volume)
