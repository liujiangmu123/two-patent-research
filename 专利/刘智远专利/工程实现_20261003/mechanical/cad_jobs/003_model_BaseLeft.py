import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('BaseLeft') is None
L=420.0
out=Part.makeBox(40,40,L,App.Vector(-20.0,-20.0,0))
inside=Part.makeBox(36,36,L+2,App.Vector(-18.0,-18.0,-1))
shape=out.cut(inside)
obj=doc.addObject('Part::Feature','BaseLeft')
obj.Shape=shape
start=App.Vector(*[-305, -210, 20]); end=App.Vector(*[-305, 210, 20])
obj.Placement=App.Placement(start,App.Rotation(App.Vector(0,0,1),end-start))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal profile; supplier details and end connection not released'
