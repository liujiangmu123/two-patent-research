import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('BallastEnvelope')
print('ClampPlate0','BallastEnvelope',a.Shape.common(b.Shape).Volume)
