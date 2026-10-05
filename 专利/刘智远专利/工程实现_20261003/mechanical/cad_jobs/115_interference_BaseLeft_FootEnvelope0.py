import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('FootEnvelope0')
print('BaseLeft','FootEnvelope0',a.Shape.common(b.Shape).Volume)
