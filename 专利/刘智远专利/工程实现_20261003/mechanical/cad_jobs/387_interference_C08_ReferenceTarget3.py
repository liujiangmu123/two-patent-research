import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('C08'); b=doc.getObject('ReferenceTarget3')
print('C08','ReferenceTarget3',a.Shape.common(b.Shape).Volume)
