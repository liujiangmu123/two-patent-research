import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('BaseFront'); b=doc.getObject('FootEnvelope2')
print('BaseFront','FootEnvelope2',a.Shape.common(b.Shape).Volume)
