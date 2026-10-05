import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
assert doc.getObject('C08') is None
points=[App.Vector(x-27.958333333333332,y-27.958333333333332,0) for x,y in [(0, 0), (100, 0), (100, 8), (8, 8), (8, 100), (0, 100), (0, 0)]]
shape=Part.Face(Part.makePolygon(points)).extrude(App.Vector(0,0,150))
obj=doc.addObject('Part::Feature','C08'); obj.Shape=shape
obj.Placement=App.Placement(App.Vector(*[-170, 120, 180]),App.Rotation(App.Vector(0,0,1),0.0))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal sharp-corner coupon; real fillets/coating/thickness need independent measurement'
