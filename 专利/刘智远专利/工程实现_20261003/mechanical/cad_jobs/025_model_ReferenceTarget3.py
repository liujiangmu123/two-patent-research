import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
obj=doc.addObject('Part::Feature','ReferenceTarget3')
obj.Shape=Part.makeSphere(20,App.Vector(*[220, 140, 650]))
obj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal matte sphere envelope; measured center and holder interfaces required'
