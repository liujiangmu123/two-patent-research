"""Prepare data and per-action scripts ONLY. Never execute FreeCAD locally."""
from pathlib import Path
import csv
import json
import math

PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = PACKAGE.parents[2]
DEST = PACKAGE / 'mechanical'
p = json.loads((DEST/'design_parameters.json').read_text(encoding='utf-8'))
SCRIPTS = DEST/'cad_jobs'
SCRIPTS.mkdir(exist_ok=True)
jobs=[]
bom=[]
parts=[]

def job(title, code, async_required=False, expected=None):
    code='import FreeCAD as App\nimport Part\n'+code+'\n'
    compile(code,title,'exec')  # syntax only: no FreeCAD import/execution here
    file=f'{len(jobs):03d}_{title}.py'
    (SCRIPTS/file).write_text(code,encoding='utf-8')
    jobs.append({'order':len(jobs),'action':title,'suggested_rpc':'execute_code_async' if async_required else 'execute_code',
                 'script':'cad_jobs/'+file,'status':'not_executed','expected':expected or title,
                 'screenshot_required':False,'do_not_retry_timeout':True})

def row(id,description,qty,length,material,notes):
    bom.append([id,description,qty,length,material,'DESIGN_ONLY_NOT_RELEASED',notes])

job('create_document',"assert 'LZT_CAL_01' not in App.listDocuments(), 'Existing document: inspect before continuing'\ndoc=App.newDocument('LZT_CAL_01')\ndoc.Label='LZT CAL 01 nominal ground calibration rig'",expected='Document exists; no existing document reset')

def tube(id,start,end,outer=40,wall=2):
    L=math.dist(start,end)
    parts.append(id)
    job('model_'+id,f"doc=App.getDocument('LZT_CAL_01')\nassert doc.getObject({id!r}) is None\nL={L!r}\nout=Part.makeBox({outer},{outer},L,App.Vector({-outer/2},{-outer/2},0))\ninside=Part.makeBox({outer-2*wall},{outer-2*wall},L+2,App.Vector({-outer/2+wall},{-outer/2+wall},-1))\nshape=out.cut(inside)\nobj=doc.addObject('Part::Feature',{id!r})\nobj.Shape=shape\nstart=App.Vector(*{start!r}); end=App.Vector(*{end!r})\nobj.Placement=App.Placement(start,App.Rotation(App.Vector(0,0,1),end-start))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal profile; supplier details and end connection not released'",True)
    row(id,f'{outer}x{outer}x{wall} nominal hollow aluminum tube',1,round(L,4),'Aluminum grade TBD','Axis length; brace cut faces/fittings require CAD and supplier confirmation')

tube('BaseFront',[-325,-230,20],[325,-230,20])
tube('BaseRear',[-325,230,20],[325,230,20])
tube('BaseLeft',[-305,-210,20],[-305,210,20])
tube('BaseRight',[305,-210,20],[305,210,20])
for i,x in enumerate(p['upright_centers_x_mm']):
    tube('Upright'+str(i),[x,230,40],[x,230,690])
tube('Crossbar',[-200,230,670],[200,230,670])
for i,(start,end) in enumerate(p['brace_centerline_endpoints_mm']):
    tube('Brace'+str(i),start,end,20,2)
for i,(x,z,L) in enumerate(zip(p['upright_centers_x_mm'],[160,380],p['coupon_arm_lengths_mm'])):
    tube('CouponArm'+str(i),[x,p['short_arm_start_y_mm'],z],[x,p['short_arm_start_y_mm']-L,z],20,2)
for i,(center,L) in enumerate(zip(p['reference_target_nominal_centers_mm'],p['reference_target_arm_lengths_mm'])):
    x=p['upright_centers_x_mm'][i%2]
    tube('TargetArm'+str(i),[x,p['short_arm_start_y_mm'],center[2]-30],[x,p['short_arm_start_y_mm']-L,center[2]-30],20,2)

for c in p['coupon_nominal_mm']:
    id=c['id']; b,t,L=c['width'],c['thickness'],c['length']
    cen=(b*b*t+t*t*(b-t))/(2*(2*b*t-t*t))
    points=[(0,0),(b,0),(b,t),(t,t),(t,b),(0,b),(0,0)]
    start=p['coupon_axis_start_mm'][id]; deg=math.degrees(p['coupon_orientation_rad'][id])
    parts.append(id)
    job('model_'+id,f"doc=App.getDocument('LZT_CAL_01')\nassert doc.getObject({id!r}) is None\npoints=[App.Vector(x-{cen!r},y-{cen!r},0) for x,y in {points!r}]\nshape=Part.Face(Part.makePolygon(points)).extrude(App.Vector(0,0,{L}))\nobj=doc.addObject('Part::Feature',{id!r}); obj.Shape=shape\nobj.Placement=App.Placement(App.Vector(*{start!r}),App.Rotation(App.Vector(0,0,1),{deg!r}))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal sharp-corner coupon; real fillets/coating/thickness need independent measurement'")
    row(id,f'L{b}x{t} steel coupon',1,L,'Steel actual grade and section measured','Nominal shape only; real hot-rolled fillets are absent')

for i,(x,z) in enumerate([(-170,170),(170,390)]):
    id='ClampPlate'+str(i); parts.append(id)
    job('model_'+id,f"doc=App.getDocument('LZT_CAL_01')\nassert doc.getObject({id!r}) is None\nshape=Part.makeBox(150,55,8,App.Vector(-75,-27.5,0))\nfor xc in [-45,45]:\n    r=3.3; half=(35-6.6)/2\n    slot=Part.makeBox(2*half,6.6,10,App.Vector(xc-half,-r,-1))\n    slot=slot.fuse(Part.makeCylinder(r,10,App.Vector(xc-half,0,-1)))\n    slot=slot.fuse(Part.makeCylinder(r,10,App.Vector(xc+half,0,-1)))\n    shape=shape.cut(slot)\nobj=doc.addObject('Part::Feature',{id!r}); obj.Shape=shape\nobj.Placement.Base=App.Vector({x},120,{z})",True)
    row(id,'150x55x8 plate with two nominal 35x6.6 slots',1,None,'Aluminum grade TBD','Inside 1.5kg brackets allowance; clamping straps/bolts not frozen')
    pad='IsolationPad'+str(i); parts.append(pad)
    job('model_'+pad,f"doc=App.getDocument('LZT_CAL_01')\nobj=doc.addObject('Part::Feature',{pad!r})\nobj.Shape=Part.makeBox(150,55,2,App.Vector({x-75},92.5,{z+8}))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Isolation pad placeholder; compression repeatability to be tested'")
    row(pad,'150x55x2 isolating pad',1,None,'Polymer grade TBD','Part of connection allowance; lower coupon contact area masked from observation')

for i,c in enumerate(p['reference_target_nominal_centers_mm']):
    id='ReferenceTarget'+str(i); parts.append(id)
    job('model_'+id,f"doc=App.getDocument('LZT_CAL_01')\nobj=doc.addObject('Part::Feature',{id!r})\nobj.Shape=Part.makeSphere(20,App.Vector(*{c!r}))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Nominal matte sphere envelope; measured center and holder interfaces required'")
    row(id,'Nominal matte spherical reference target D40',1,None,'Vendor certified/independently measured','Hollow/solid material TBD; mass inside 0.9kg feet+target allowance')
for i,(x,y) in enumerate(p['feet']['centers_xy_mm']):
    id='FootEnvelope'+str(i); parts.append(id)
    job('model_'+id,f"doc=App.getDocument('LZT_CAL_01')\nobj=doc.addObject('Part::Feature',{id!r})\nobj.Shape=Part.makeCylinder(25,5,App.Vector({x},{y},-5))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Support envelope only; M8 supplier foot and threaded interface not modeled'")
    row(id,'M8 leveling foot, D50 pad, 20 travel',1,None,'Procured part TBD','Support envelope only; real thread/locknuts to be added after selection')

tray=p['ballast_tray_mm']; parts.append('BallastTray')
job('model_BallastTray',f"doc=App.getDocument('LZT_CAL_01')\nobj=doc.addObject('Part::Feature','BallastTray')\nobj.Shape=Part.makeBox(*{tray['size']!r},App.Vector(*{tray['origin']!r}))")
row('BallastTray','300x110x3 ballast support tray',1,None,'Aluminum grade TBD','Inside brackets mass allowance; retaining strap and crush sleeves required')
size=p['ballast_nominal_size_mm']; center=p['ballast_center_mm']; origin=[c-s/2 for c,s in zip(center,size)]; parts.append('BallastEnvelope')
job('model_BallastEnvelope',f"doc=App.getDocument('LZT_CAL_01')\nobj=doc.addObject('Part::Feature','BallastEnvelope')\nobj.Shape=Part.makeBox(*{size!r},App.Vector(*{origin!r}))\nobj.addProperty('App::PropertyString','DesignStatus').DesignStatus='Approximate 3kg steel ballast; requires mechanical retention'")
row('BallastEnvelope','260x60x24.5 steel weight ~3kg',1,None,'Steel','Use unless measured mass and CG meet assumptions; lock into tray')
row('CONNECTIONS','Corner/gusset plates, M6 fasteners, sleeves, clamp/retaining straps',None,None,'Procured/custom fittings TBD','1.5kg total allowance includes two Al plates, tray and pads; counts/hole patterns not frozen')
row('HOLDERS','Target offset holders, M8 nuts and leveling hardware',None,None,'Procured fittings TBD','0.9kg total allowance includes targets/feet; confirm manufacturer dimensions before drawings')

job('recompute',"doc=App.getDocument('LZT_CAL_01')\ndoc.recompute()",True)
job('check_shape_validity',"doc=App.getDocument('LZT_CAL_01')\nprint([(obj.Name,obj.Shape.isValid(),len(obj.Shape.Solids),obj.Shape.Volume) for obj in doc.Objects if hasattr(obj,'Shape')])",expected='Every planned shape valid and one solid; no procurement fittings falsely marked complete')
# One pair per heavy RPC; do not combine model/export/screenshot with collision checks.
for i,a in enumerate(parts):
    for b in parts[i+1:]:
        job('interference_'+a+'_'+b,f"doc=App.getDocument('LZT_CAL_01')\na=doc.getObject({a!r}); b=doc.getObject({b!r})\nprint({a!r},{b!r},a.Shape.common(b.Shape).Volume)",True,expected='Investigate nonzero common volume; touching contact may be allowed only after inspection')

model_dir=WORKSPACE/'建模工程/模型/V1_LZT_CAL_20261003'
fcstd=model_dir/'LZT_CAL_01.FCStd'; step=model_dir/'LZT_CAL_01.step'
job('save_document',f"doc=App.getDocument('LZT_CAL_01')\ndoc.saveAs({str(fcstd)!r})",expected='Saved only after upstream geometry review; verify next')
job('verify_saved_file',f"import os\nprint(os.path.isfile({str(fcstd)!r}),os.path.getsize({str(fcstd)!r}) if os.path.isfile({str(fcstd)!r}) else 0)\nprint(list(App.listDocuments()))",expected='File exists with nonzero size; document listed')
job('export_STEP',f"doc=App.getDocument('LZT_CAL_01')\nPart.export([obj for obj in doc.Objects if hasattr(obj,'Shape')],{str(step)!r})",True,expected='STEP exported only after saved file verification; check file and re-import separately')
job('verify_STEP_file',f"import os\nprint(os.path.isfile({str(step)!r}),os.path.getsize({str(step)!r}) if os.path.isfile({str(step)!r}) else 0)")

manifest={'schema_version':'trusstwin.pending-cad/0.1','status':'ALL_JOBS_NOT_EXECUTED',
          'requires':['Locate and read mandatory global FreeCAD MCP SKILL.md','Start only the required unified launcher','Inspect actual RPC schema and map suggested calls','Create intended model directory with normal file tools','Inspect installed document, ping and empty version probe before mutation'],
          'not_a_model_or_drawing':True,'planned_object_count':len(parts),'output_directory':str(model_dir),'jobs':jobs,
          'remaining_supplier_details':['Fasteners, bolt hole pitch, crush sleeves, clamp straps, target holders and leveling foot threads','Actual tube cross section, brace end cuts, coupon fillets and isolation pad properties','Detailed retaining strap and tray attachment'],
          'remaining_CAD_actions':['Inspect contact/visibility/tool access from front, side, rear and elevated views','Model frozen fittings and check interference again','Separate TechDraw tasks with assembly dimensions and each manufactured part drawing','Re-import STEP and verify units/coordinates; save screenshots per request'],
          'timeout_discipline':'Never repeat the timed-out mutation; inspect writes first. No manual uvx or local source startup.'}
(DEST/'cad_jobs.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with (DEST/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(['id','description','quantity','nominal_axis_length_mm','material','release_status','notes']); w.writerows(bom)
with (DEST/'physical_test_record.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(['rig_serial','date','operator','test','measurement','unit','uncertainty','acceptance_basis','result','evidence_file'])
    for test,unit,basis in [('mass','kg','measured>=7 and actual assembly configuration recorded'),('center_of_gravity_offset','mm','total planar offset<=50, both x/y verified'),('reference_coordinate_repeatability','mm','match declared metrology uncertainty; target value not yet established'),('clamp_slip','mm','no slip beyond calibration budget under actual specimen load'),('support_lateral_pull','N','load path and overturning checked at declared wind force with controlled test'),('temperature','K','difference<=3 for unchanged control coordinates'),('wind','m/s','<=5 for calibration'),('foot_settlement','mm','before/after control geometry within validated budget')]:
        w.writerow(['','','',test,'',unit,'',basis,'NOT_TESTED',''])
print(json.dumps({'planned_shapes':len(parts),'pending_jobs':len(jobs),'bom_rows':len(bom),'cad_executed':False},ensure_ascii=False))
