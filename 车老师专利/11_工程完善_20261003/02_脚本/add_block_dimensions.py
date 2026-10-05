import FreeCAD as App
import Part
doc=App.getDocument('CheBlockDrawingV2');page=doc.Page
doc.Right.XDirection=App.Vector(0,1,0)
report=[]
for name,target,kind,x,y in [('Front',250,'DistanceX',110,72),('Front',62,'DistanceY',12,118),('Top',90,'DistanceY',12,200)]:
    view=doc.getObject(name)
    matches=[]
    for i in range(1,1000):
        try:
            edge=view.getEdgeBySelection('Edge'+str(i)).Edges[0]
            if isinstance(edge.Curve,Part.Line) and abs(edge.Length-target)<.01:matches.append('Edge'+str(i))
        except Exception:break
    assert matches,(name,target)
    dim=doc.addObject('TechDraw::DrawViewDimension','Dim'+name+str(target))
    dim.Type=kind;dim.References2D=[(view,[matches[0]])];dim.X=x;dim.Y=y
    page.addView(dim)
    report.append({'view':name,'edge':matches[0],'target_mm':target})
doc.recompute()
_result_={'dimensions':report}
