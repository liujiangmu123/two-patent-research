import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('IsolationPad0'); b=doc.getObject('FootEnvelope3')
print('IsolationPad0','FootEnvelope3',a.Shape.common(b.Shape).Volume)
