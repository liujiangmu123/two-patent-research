import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('FootEnvelope0')
print('ClampPlate0','FootEnvelope0',a.Shape.common(b.Shape).Volume)
