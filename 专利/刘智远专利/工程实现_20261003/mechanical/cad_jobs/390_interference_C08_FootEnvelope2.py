import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C08'); b=doc.getObject('FootEnvelope2')
print('C08','FootEnvelope2',a.Shape.common(b.Shape).Volume)
