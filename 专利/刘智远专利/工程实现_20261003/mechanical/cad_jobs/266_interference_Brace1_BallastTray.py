import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
a=doc.getObject('Brace1'); b=doc.getObject('BallastTray')
print('Brace1','BallastTray',a.Shape.common(b.Shape).Volume)
