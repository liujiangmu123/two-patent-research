import FreeCAD as App
import FreeCADGui as Gui
import TechDraw
import Part
name='CheBlockDrawingV2'
assert name not in App.listDocuments(),'Drawing document already exists; inspect before retry'
doc=App.newDocument(name)
source=doc.addObject('Part::Feature','BlockSource')
source.Shape=next(p['shape'] for p in App._che_core_parts if p['no']=='BL-01').copy()
source.Label='BL-01_阀块_V2_双测温双泄压'
source.ViewObject.Visibility=False
page=doc.addObject('TechDraw::DrawPage','Page')
template=doc.addObject('TechDraw::DrawSVGTemplate','Template')
template.Template='C:/Users/Administrator/AppData/Local/Programs/FreeCAD 1.1/data/Mod/TechDraw/Templates/ISO/A3_Landscape_ISO5457_minimal.svg'
page.Template=template
for label,direction,x,y in [('Front',App.Vector(0,-1,0),110,118),('Top',App.Vector(0,0,1),110,200),('Right',App.Vector(1,0,0),267,118)]:
    v=doc.addObject('TechDraw::DrawViewPart',label)
    v.Source=[source];v.Direction=direction;v.Scale=.7;v.X=x;v.Y=y
    page.addView(v)
note=doc.addObject('TechDraw::DrawViewAnnotation','DesignNotes')
note.Text=['BL-01 / CHE-V2-20261003 / nominal custom design','250 x 90 x 62 mm; 45 steel, heat treatment pending','4 x M22x1.5: Wandfluh 3-395.4 / sheet 2.13-1008','2 x nominal M20 thermal relief interfaces; procurement pending','4 x M8 mounting: (10,25),(10,65),(242,25),(242,65)','Dowel: (28,20),(222,70); actual orifice diameter 0.1 mm','C and R thermowells are independent, closed tip','Threads are envelopes. Not a released manufacturing drawing.']
note.TextSize=3.2;note.X=286;note.Y=220;page.addView(note)
title=doc.addObject('TechDraw::DrawViewAnnotation','Title')
title.Text=['TAILSTOCK LOCKING BLOCK / V2','Native FreeCAD TechDraw orthographic views','Dimensions mm / source: live FreeCAD MCP']
title.TextSize=4;title.X=210;title.Y=36;page.addView(title)
doc.recompute()
Gui.activeDocument().activeView().fitAll()
App._che_drawing_doc=name
views={}
for n in ('Front','Top','Right'):
    v=doc.getObject(n);edges=[]
    for i in range(1,1000):
        try:
            edge=v.getEdgeByIndex(i)
            if edge.isNull():break
            if isinstance(edge.Curve,Part.Line):
                edges.append({'edge':'Edge'+str(i),'length':edge.Length,'ends':[list(vertex.Point) for vertex in edge.Vertexes]})
        except Exception:break
    views[n]=edges
_result_={'doc':name,'page':page.Name,'linear_edges':views}
