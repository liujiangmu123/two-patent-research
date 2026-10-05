import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget3'); b=doc.getObject('FootEnvelope2')
print('ReferenceTarget3','FootEnvelope2',a.Shape.common(b.Shape).Volume)
