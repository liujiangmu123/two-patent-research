import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
obj=doc.addObject('Part::Feature','BallastEnvelope')
obj.Shape=Part.makeBox(*[260, 60, 24.5],App.Vector(*[-130.0, -230.0, 43.0]))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Approximate 3kg steel ballast; requires mechanical retention'
