import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Crossbar'); b=doc.getObject('FootEnvelope2')
print('Crossbar','FootEnvelope2',a.Shape.common(b.Shape).Volume)
