import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('Upright0') is None
L=650.0
out=Part.makeBox(40,40,L,App.Vector(-20.0,-20.0,0))
inside=Part.makeBox(36,36,L+2,App.Vector(-18.0,-18.0,-1))
shape=out.cut(inside)
obj=doc.addObject('Part::Feature','Upright0')
obj.Shape=shape
start=App.Vector(*[-220, 230, 40]); end=App.Vector(*[-220, 230, 690])
obj.Placement=App.Placement(start,App.Rotation(App.Vector(0,0,1),end-start))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal profile; supplier details and end connection not released'
