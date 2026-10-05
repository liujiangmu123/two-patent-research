import FreeCAD as App
import Part
summary = {}
for name, shape in App._che_vendor.items():
    solids=[]
    for s in shape.Solids:
        bb=s.BoundBox
        solids.append({'volume':s.Volume,'bbox':[bb.XMin,bb.XMax,bb.YMin,bb.YMax,bb.ZMin,bb.ZMax]})
    axial=[]
    for f in shape.Faces:
        c=f.Surface
        if isinstance(c,Part.Cylinder) and abs(c.Axis.x)>.99:
            bb=f.BoundBox
            axial.append([round(c.Radius,3),round(bb.XMin,3),round(bb.XMax,3),round(f.Area,3)])
    summary[name]={'solids':solids,'axial':axial}
_result_=summary
