import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate1'); b=doc.getObject('FootEnvelope3')
print('ClampPlate1','FootEnvelope3',a.Shape.common(b.Shape).Volume)
