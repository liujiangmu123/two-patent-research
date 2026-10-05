import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseLeft'); b=doc.getObject('FootEnvelope2')
print('BaseLeft','FootEnvelope2',a.Shape.common(b.Shape).Volume)
