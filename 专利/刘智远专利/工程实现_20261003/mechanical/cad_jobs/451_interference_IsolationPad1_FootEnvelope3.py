import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad1'); b=doc.getObject('FootEnvelope3')
print('IsolationPad1','FootEnvelope3',a.Shape.common(b.Shape).Volume)
