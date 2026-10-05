import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget3'); b=doc.getObject('FootEnvelope0')
print('ReferenceTarget3','FootEnvelope0',a.Shape.common(b.Shape).Volume)
