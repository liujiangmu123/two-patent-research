import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('FootEnvelope2'); b=doc.getObject('FootEnvelope3')
print('FootEnvelope2','FootEnvelope3',a.Shape.common(b.Shape).Volume)
