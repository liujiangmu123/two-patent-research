import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
obj=doc.addObject('Part::Feature','IsolationPad1')
obj.Shape=Part.makeBox(150,55,2,App.Vector(95,92.5,398))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Isolation pad placeholder; compression repeatability to be tested'
