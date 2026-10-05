import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget2'); b=doc.getObject('FootEnvelope1')
print('ReferenceTarget2','FootEnvelope1',a.Shape.common(b.Shape).Volume)
