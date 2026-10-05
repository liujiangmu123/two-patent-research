import FreeCAD as App
import FreeCADGui as Gui
import json
from pathlib import Path
assert App._che_job['stage']=='fine_bench' and App._che_job['status']=='done',App._che_job
name='CheBenchV2'
if name in App.listDocuments():
    doc=App.getDocument(name)
    old={o.EngineeringPartNo:o for o in doc.Objects if 'EngineeringPartNo' in o.PropertiesList}
else:
    doc=App.newDocument(name);old={}
groups={o.Name[6:]:o for o in doc.Objects if o.Name.startswith('Group_')}
palette={'Frame':(.48,.51,.55),'Bed':(.38,.47,.55),'Loader':(.73,.75,.78),'Tailstock':(.6,.67,.73),'TailHydraulics':(.36,.47,.6),'Thermal':(.25,.52,.72),'Guard':(.72,.79,.81),'Sensors':(.78,.66,.32),'Power':(.29,.55,.44),'Controls':(.85,.87,.88),'Chuck':(.5,.51,.55)}
for i,p in enumerate(App._che_bench_parts):
    group=p['group']
    if group not in groups:groups[group]=doc.addObject('App::DocumentObjectGroup','Group_'+group)
    o=old.get(p['no']) or doc.addObject('Part::Feature','Part_'+str(i+1).zfill(4))
    o.Shape=p['shape'];o.Label=p['no']+'_'+p['name']
    for key,v in (('EngineeringPartNo',p['no']),('EngineeringGroup',group),('MaterialSpec',p['material']),('GeometryBasis',p['basis']),('DesignNotes',p['notes']),('MotionGroup',p['moving'])):
        if key not in o.PropertiesList:o.addProperty('App::PropertyString',key,'Engineering')
        setattr(o,key,v)
    o.ViewObject.ShapeColor=palette.get(group,(.38,.39,.40));o.ViewObject.LineColor=(.15,.15,.15)
    o.ViewObject.Visibility=True
    if p['material']=='PC':o.ViewObject.Transparency=80
    groups[group].addObject(o)
doc.recompute()
Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
App._che_bench_doc=doc.Name
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003')
(root/'04_检查/精细试验台零件清单.json').write_text(json.dumps({'parts':App._che_job['summary'],'part_count':len(App._che_bench_parts)},ensure_ascii=False,indent=2),encoding='utf-8')
_result_={'document':doc.Name,'parts':len(App._che_bench_parts)}
