import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
obj=doc.addObject('Part::Feature','FootEnvelope3')
obj.Shape=Part.makeCylinder(25,5,App.Vector(280,230,-5))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Support envelope only; M8 supplier foot and threaded interface not modeled'
