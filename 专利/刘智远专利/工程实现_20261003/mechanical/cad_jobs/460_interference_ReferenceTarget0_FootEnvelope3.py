import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget0'); b=doc.getObject('FootEnvelope3')
print('ReferenceTarget0','FootEnvelope3',a.Shape.common(b.Shape).Volume)
