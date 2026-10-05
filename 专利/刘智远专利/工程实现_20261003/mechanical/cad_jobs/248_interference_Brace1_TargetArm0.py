import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace1'); b=doc.getObject('TargetArm0')
print('Brace1','TargetArm0',a.Shape.common(b.Shape).Volume)
