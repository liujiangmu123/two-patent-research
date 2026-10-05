import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('Crossbar') is None
L=400.0
out=Part.makeBox(40,40,L,App.Vector(-20.0,-20.0,0))
inside=Part.makeBox(36,36,L+2,App.Vector(-18.0,-18.0,-1))
shape=out.cut(inside)
obj=doc.addObject('Part::Feature','Crossbar')
obj.Shape=shape
start=App.Vector(*[-200, 230, 670]); end=App.Vector(*[200, 230, 670])
obj.Placement=App.Placement(start,App.Rotation(App.Vector(0,0,1),end-start))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal profile; supplier details and end connection not released'
