import FreeCAD as App
import Part
doc=App.getDocument('CheBlockDrawingV2')
out={}
for n in ('Front','Top','Right'):
    v=doc.getObject(n);v.ScaleType='Custom';v.Scale=.7
doc.recompute()
for n in ('Front','Top','Right'):
    v=doc.getObject(n);edges=[]
    for i in range(0,1000):
        try:
            shape=v.getEdgeByIndex(i)
            if shape.isNull():
                if i==0:continue
                break
            e=shape.Edges[0]
            if isinstance(e.Curve,Part.Line):
                edges.append({'index':i,'edge':'Edge'+str(i),'length':e.Length,'ends':[list(p.Point) for p in e.Vertexes]})
        except Exception as exc:
            if i==0:continue
            edges.append({'error':str(exc),'index':i});break
    out[n]=edges
_result_={'scale':.7,'edges':out}
