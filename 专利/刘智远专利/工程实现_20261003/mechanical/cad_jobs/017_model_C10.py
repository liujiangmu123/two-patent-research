import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('C10') is None
points=[App.Vector(x-28.68421052631579,y-28.68421052631579,0) for x,y in [(0, 0), (100, 0), (100, 10), (10, 10), (10, 100), (0, 100), (0, 0)]]
shape=Part.Face(Part.makePolygon(points)).extrude(App.Vector(0,0,150))
obj=doc.addObject('Part::Feature','C10'); obj.Shape=shape
obj.Placement=App.Placement(App.Vector(*[170, 120, 400]),App.Rotation(App.Vector(0,0,1),180.0))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal sharp-corner coupon; real fillets/coating/thickness need independent measurement'
