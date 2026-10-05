import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('FootEnvelope0')
print('BaseFront','FootEnvelope0',a.Shape.common(b.Shape).Volume)
