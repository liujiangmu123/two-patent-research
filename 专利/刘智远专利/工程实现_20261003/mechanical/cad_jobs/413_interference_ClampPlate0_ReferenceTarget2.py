import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('ReferenceTarget2')
print('ClampPlate0','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
