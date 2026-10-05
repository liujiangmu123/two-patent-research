import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ReferenceTarget1'); b=doc.getObject('FootEnvelope2')
print('ReferenceTarget1','FootEnvelope2',a.Shape.common(b.Shape).Volume)
