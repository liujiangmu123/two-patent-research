import FreeCAD as App
import FreeCADGui as Gui
import json
from pathlib import Path
assert App._che_job['status']=='done',App._che_job
assert 'CheTailstockV2' not in App.listDocuments(),'Existing working document must be reviewed before replacing.'
doc=App.newDocument('CheTailstockV2')
doc.Label='车老师_精细尾座阀块油缸_V2'
groups={}
palette={'Cylinder':(.7,.73,.78),'Block':(.32,.45,.60),'Valves':(.22,.23,.25),'Sensors':(.8,.8,.83),'Fasteners':(.35,.36,.39),'Seals':(.14,.14,.15),'Ports':(.77,.65,.36)}
for i,p in enumerate(App._che_core_parts):
    group=p['group']
    if group not in groups:
        groups[group]=doc.addObject('App::DocumentObjectGroup','Group_'+group)
    obj=doc.addObject('Part::Feature','Part_'+str(i+1).zfill(3))
    obj.Label=p['no']+'_'+p['name'];obj.Shape=p['shape']
    for key,value in (('EngineeringPartNo',p['no']),('EngineeringGroup',group),('MaterialSpec',p['material']),('GeometryBasis',p['basis']),('ThreadSpec',p['thread']),('DesignNotes',p['notes'])):
        obj.addProperty('App::PropertyString',key,'Engineering');setattr(obj,key,value)
    obj.addProperty('App::PropertyBool','MovesWithPiston','Engineering');obj.MovesWithPiston=p['moving']
    obj.ViewObject.ShapeColor=palette.get(group,(.6,.6,.6));obj.ViewObject.LineColor=(.12,.12,.12)
    groups[group].addObject(obj)
g=doc.addObject('App::DocumentObjectGroup','HydraulicNetworks');g.Label='孔系网络_检验参考_隐藏'
for i,(key,shape) in enumerate(App._che_core_nets.items()):
    obj=doc.addObject('Part::Feature','Network_'+str(i+1));obj.Label=key;obj.Shape=shape
    obj.addProperty('App::PropertyBool','VirtualGeometry','Engineering');obj.VirtualGeometry=True
    g.addObject(obj);obj.ViewObject.Visibility=False
doc.addObject('App::FeaturePython','DesignParameters')
p=doc.getObject('DesignParameters');p.Label='设计基准_名义结构_待实物验证'
p.addProperty('App::PropertyLength','Bore','Design');p.Bore=63
p.addProperty('App::PropertyLength','Rod','Design');p.Rod=35
p.addProperty('App::PropertyLength','Stroke','Design');p.Stroke=140
p.addProperty('App::PropertyLength','Extension','Design');p.Extension=70
p.addProperty('App::PropertyString','VerificationStatus','Design');p.VerificationStatus='Nominal development design; vendor/physical tests pending'
doc.recompute()
Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
App._che_core_doc=doc.Name
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003')
report={'document':doc.Name,'part_count':len(App._che_core_parts),'parts':App._che_job['summary'],'elapsed_s':App._che_job['elapsed_s']}
(root/'04_检查/精细核心零件清单.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
_result_={'document':doc.Name,'parts':len(App._che_core_parts),'networks':len(App._che_core_nets)}
