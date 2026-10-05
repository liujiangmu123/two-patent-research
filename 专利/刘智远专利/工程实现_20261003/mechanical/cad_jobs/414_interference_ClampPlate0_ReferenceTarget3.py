import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('ClampPlate0'); b=doc.getObject('ReferenceTarget3')
print('ClampPlate0','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
