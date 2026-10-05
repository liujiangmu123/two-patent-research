import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('FootEnvelope1')
print('C10','FootEnvelope1',a.Shape.common(b.Shape).Volume)
