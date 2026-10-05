import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate1'); b=doc.getObject('FootEnvelope0')
print('ClampPlate1','FootEnvelope0',a.Shape.common(b.Shape).Volume)
