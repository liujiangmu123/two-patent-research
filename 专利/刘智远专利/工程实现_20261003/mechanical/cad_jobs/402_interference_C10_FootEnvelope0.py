import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C10'); b=doc.getObject('FootEnvelope0')
print('C10','FootEnvelope0',a.Shape.common(b.Shape).Volume)
