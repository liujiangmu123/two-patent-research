import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate1'); b=doc.getObject('ReferenceTarget2')
print('ClampPlate1','ReferenceTarget2',a.Shape.common(b.Shape).Volume)
