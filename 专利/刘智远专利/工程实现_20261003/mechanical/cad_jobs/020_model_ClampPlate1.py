import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('ClampPlate1') is None
shape=Part.makeBox(150,55,8,App.Vector(-75,-27.5,0))
for xc in [-45,45]:
    r=3.3; half=(35-6.6)/2
    slot=Part.makeBox(2*half,6.6,10,App.Vector(xc-half,-r,-1))
    slot=slot.fuse(Part.makeCylinder(r,10,App.Vector(xc-half,0,-1)))
    slot=slot.fuse(Part.makeCylinder(r,10,App.Vector(xc+half,0,-1)))
    shape=shape.cut(slot)
obj=doc.addObject('Part::Feature','ClampPlate1'); obj.Shape=shape
obj.Placement.Base=App.Vector(170,120,390)
