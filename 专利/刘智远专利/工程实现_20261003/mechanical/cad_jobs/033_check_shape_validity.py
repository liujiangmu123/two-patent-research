import FreeCAD as App
import Part
doc=App.getDocument('LZT_CAL_01')
print([(obj.Name,obj.Shape.isValid(),len(obj.Shape.Solids),obj.Shape.Volume) for obj in doc.Objects if hasattr(obj,'Shape')])
