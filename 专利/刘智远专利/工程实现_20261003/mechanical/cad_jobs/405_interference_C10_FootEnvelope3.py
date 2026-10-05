import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('FootEnvelope3')
print('C10','FootEnvelope3',a.Shape.common(b.Shape).Volume)
