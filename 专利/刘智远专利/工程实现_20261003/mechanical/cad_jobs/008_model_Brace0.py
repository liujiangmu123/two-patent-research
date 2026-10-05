import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('Brace0') is None
L=772.0103626247513
out=Part.makeBox(20,20,L,App.Vector(-10.0,-10.0,0))
inside=Part.makeBox(16,16,L+2,App.Vector(-8.0,-8.0,-1))
shape=out.cut(inside)
obj=doc.addObject('Part::Feature','Brace0')
obj.Shape=shape
start=App.Vector(*[-250, -230, 50]); end=App.Vector(*[-250, 230, 670])
obj.Placement=App.Placement(start,App.Rotation(App.Vector(0,0,1),end-start))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal profile; supplier details and end connection not released'
