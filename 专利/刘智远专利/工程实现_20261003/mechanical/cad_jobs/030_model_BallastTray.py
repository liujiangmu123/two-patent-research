import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
obj=doc.addObject('Part::Feature','BallastTray')
obj.Shape=Part.makeBox(*[300, 110, 3],App.Vector(*[-150, -235, 40]))
