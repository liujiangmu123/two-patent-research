import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C08'); b=doc.getObject('ClampPlate0')
print('C08','ClampPlate0',a.Shape.common(b.Shape).Volume)
