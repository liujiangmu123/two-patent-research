import FreeCAD as App
import json
from pathlib import Path
assert App._che_core_parts
doc=App.getDocument(App._che_core_doc)
by_no={o.EngineeringPartNo:o for o in doc.Objects if 'EngineeringPartNo' in o.PropertiesList}
for p in App._che_core_parts:
    o=by_no.get(p['no'])
    if o is None:
        o=doc.addObject('Part::Feature','Extra_'+p['no'])
        for key,value in (('EngineeringPartNo',p['no']),('EngineeringGroup',p['group']),('MaterialSpec',p['material']),('GeometryBasis',p['basis']),('ThreadSpec',p['thread']),('DesignNotes',p['notes'])):
            o.addProperty('App::PropertyString',key,'Engineering');setattr(o,key,value)
        o.addProperty('App::PropertyBool','MovesWithPiston','Engineering');o.MovesWithPiston=p['moving']
        doc.getObject('Group_'+p['group']).addObject(o)
    o.Shape=p['shape'];o.Label=p['no']+'_'+p['name'];o.GeometryBasis=p['basis'];o.DesignNotes=p['notes']
by_net={o.Label:o for o in doc.getObject('HydraulicNetworks').Group}
for key,s in App._che_core_nets.items():
    o=by_net.get(key)
    if o is None:
        o=doc.addObject('Part::Feature','Extra_Network');o.Label=key
        o.addProperty('App::PropertyBool','VirtualGeometry','Engineering');o.VirtualGeometry=True
        doc.getObject('HydraulicNetworks').addObject(o);o.ViewObject.Visibility=False
    o.Shape=s
doc.recompute()
root=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利/11_工程完善_20261003')
(root/'04_检查/精细核心零件清单.json').write_text(json.dumps({'parts':[{k:v for k,v in p.items() if k!='shape'}|{'valid':p['shape'].isValid(),'solids':len(p['shape'].Solids),'volume_mm3':p['shape'].Volume} for p in App._che_core_parts],'part_count':len(App._che_core_parts)},ensure_ascii=False,indent=2),encoding='utf-8')
_result_={'updated':len(App._che_core_parts)}
