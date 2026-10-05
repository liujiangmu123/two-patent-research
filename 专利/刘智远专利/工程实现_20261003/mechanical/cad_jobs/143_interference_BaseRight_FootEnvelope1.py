import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseRight'); b=doc.getObject('FootEnvelope1')
print('BaseRight','FootEnvelope1',a.Shape.common(b.Shape).Volume)
