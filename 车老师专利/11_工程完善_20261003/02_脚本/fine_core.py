"""Fine nominal engineering geometry; imported and executed only via live FreeCAD MCP.

Threads use specified nominal envelopes. Vendor STEP solids are unmodified source
geometry; procurement, seal detail and tolerance choices remain reviewable assumptions.
No original model, baseline or source builder is modified.
"""
import ast
import copy
import json
import math
from pathlib import Path
import FreeCAD as App
import Part
V=App.Vector
ROOT=Path('H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/车老师专利')
OUT=ROOT/'11_工程完善_20261003'
SRC=ROOT/'P5_液压尾座集成锁闭阀块_实用新型/07_脚本/p5_build_model.py'
tree=ast.parse(SRC.read_text(encoding='utf-8'))
tree.body=[n for n in tree.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='main')]
old={'__file__':str(SRC),'__name__':'p5_reference_geometry'}
exec(compile(tree,str(SRC),'exec'),old)
box,cz,cx,cy,fuse,hexprism,revolve=[old[n] for n in ('box','cz','cx','cy','fuse','hexprism','revolve_profile')]
B=copy.deepcopy(old['B'])
# Move vertical mounting fasteners away from axial cylinder tie rods and locating pins.
for config in (B,old['B']):
    config['安装与密封']['连接螺栓']['位置']=[[10,25],[10,65],[242,25],[242,65]]
    config['安装与密封']['定位销']['位置']=[[28,20],[222,70]]
PARTS=[]
NETS={}
def add(no,name,shape,group='Cylinder',material='45 steel',basis='nominal custom design',moving=False,thread='',notes=''):
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError('Invalid/non-solid part '+no+' '+name)
    PARTS.append(dict(no=no,name=name,shape=shape,group=group,material=material,basis=basis,moving=moving,thread=thread,notes=notes))

def ax(d,x0,x1,y=45,z=-45): return cx(d,x0,x1,y,z)
def ringx(od,id,x0,x1,y=45,z=-45): return ax(od,x0,x1,y,z).cut(ax(id,x0-.1,x1+.1,y,z))
def ellipse_ring(rc,ra,ta,t,p,d):
    """Continuous elliptic installed elastomer section, no polygonal pseudo seal."""
    d=V(d); d.normalize()
    u=V(0,1,0) if abs(d.y)<.9 else V(1,0,0)
    u=u-d*u.dot(d); u.normalize()
    c=p+d*t+u*rc
    # Part.Ellipse major/minor directions are explicit, avoiding ambiguous placement.
    if ta>=ra:
        e=Part.Ellipse(c+d*ta,c+u*ra,c)
    else:
        e=Part.Ellipse(c+u*ra,c+d*ta,c)
    return Part.Face(Part.Wire(e.toShape())).revolve(p,d,360)

def tie_holes(shape,x0,x1):
    holes=[ax(10.4,x0-.1,x1+.1,y,z) for y in (8,82) for z in (-8,-82)]
    return shape.cut(Part.makeCompound(holes)).removeSplitter()

def build_cylinder():
    # End cap spigots include real static seal grooves and separate installed O rings.
    f=fuse(box(0,34,0,90,-90,0),ax(69.9,33.99,40))
    f=f.cut(ax(35.1,-.1,40.1))
    for a,b,d in ((0,3,43),(5,10,43),(13,18,43),(19,30,40)):
        f=f.cut(ax(d,a,b))
    f=f.cut(ringx(71,66,35.2,38.8))
    r=fuse(box(216,250,0,90,-90,0),ax(69.9,210,216.01))
    r=r.cut(ringx(71,66,211.2,214.8))
    # Optional axial reference for calibration/rebasing, catalogue envelope pending.
    r=r.cut(ax(8.2,209.99,238)).cut(ax(16,238,250.01))
    for y,z in ((12.5,-45),(77.5,-45),(45,-12.5),(45,-77.5)):
        r=r.cut(ax(6,238,250.01,y,z)).cut(ax(5,235,238,y,z))
    pR=fuse(cz(10,-24,.01,24),old['tip'](10,V(24,45,-24),V(0,0,-1)),cx(8,24,40.01,45,-18))
    pC=fuse(cz(10,-24,.01,226),old['tip'](10,V(226,45,-24),V(0,0,-1)),cx(8,209.99,226,45,-18))
    f=f.cut(pR); r=r.cut(pC)
    # Nominal M8 full thread 17 mm, drill depth 20 mm; drilling does not cross tie rods.
    for x,y in B['安装与密封']['连接螺栓']['位置']:
        target=f if x<34 else r
        target=target.cut(cz(8,-17,.01,x,y)).cut(cz(6.8,-20,-17,x,y))
        target=target.cut(old['tip'](6.8,V(x,y,-20),V(0,0,-1)))
        if x<34:f=target
        else:r=target
    for x,y in B['安装与密封']['定位销']['位置']:
        if x<34:f=f.cut(cz(6,-6.1,.01,x,y))
        else:r=r.cut(cz(6,-6.1,.01,x,y))
    for x in (10,242):
        for y in (18,72):
            hole=fuse(cz(8,-90.01,-73,x,y),cz(6.8,-73,-70,x,y),old['tip'](6.8,V(x,y,-70),V(0,0,1)))
            if x<34:f=f.cut(hole)
            else:r=r.cut(hole)
    b=box(34,216,0,90,-90,-.5)
    b=b.cut(ax(63,39.99,210.01)).cut(ax(70,33.99,40)).cut(ax(70,210,216.01))
    f=tie_holes(f,0,40);b=tie_holes(b,34,216);r=tie_holes(r,210,250)
    add('CY-01','前端盖_杆封与导向槽',f,thread='M8x1.25 depth 17; 2 holes')
    add('CY-02','缸筒_63H8_端盖止口70',b)
    add('CY-03','后端盖_无杆腔油口',r,thread='M8x1.25 depth 17; 2 holes')
    NETS.update(Cylinder_R=pR,Cylinder_C=pC)
    for idx,t in enumerate((37,213),1):
        add('SE-CAP-'+str(idx),'端盖止口O圈_安装压缩状态',ellipse_ring(34,.99,1.76,t,V(0,45,-45),V(1,0,0)),group='Seals',material='NBR70',basis='nominal 66x2.65 ring, installed ellipse',notes='Installed area approximately preserves stock section; gland needs seal vendor confirmation.')
    add('GD-01','前端盖青铜导向套',ringx(39.9,35.1,19.05,29.95),material='CuSn12',notes='Nominal clearance .05 radial at rod; final fit to be toleranced.')
    for no,name,a,b in (('SE-W','杆端防尘圈',.05,2.95),('SE-R1','杆封_第一道',5.05,9.95),('SE-R2','杆封_第二道',13.05,17.95)):
        s=ringx(42.9,35,a,b)
        if no!='SE-W':
            # U cup opening faces pressurised cylinder interior (+X).
            s=s.cut(ringx(41.5,36.5,a+1,b+.1))
        add(no,name,s,group='Seals',material='PU/NBR',basis='nominal seal design, final catalogue selection pending')
    # Exact 140 mm stop-to-stop stroke: 170 mm chamber length minus 29+0.5+0.5 piston.
    rear=139.5;front=110.5
    piston=ringx(62.9,24.2,front,rear)
    for a,b,root in ((front+3,front+7,60.5),(front+10,front+19,57),(front+22,front+26,60.5)):
        piston=piston.cut(ringx(64,root,a,b))
    piston=piston.cut(ax(38,rear-10,rear+.1))
    piston=fuse(piston,ringx(42,35.2,front-.5,front+.01),ringx(48,38,rear-.01,rear+.5))
    add('CY-04','活塞_密封与导向槽_内沉锁紧螺母',piston,moving=True)
    rod=fuse(ax(35,-80,front),ax(24,front, rear-.45),ax(24,-98,-80))
    rod=rod.cut(ax(8.2,rear-.45-190,rear-.44))
    add('CY-05','镀铬活塞杆_两端M24连接',rod,moving=True,material='45 steel hard chrome',thread='M24x1.5 piston/nose; thread envelopes')
    nut=hexprism(30,V(rear-8.5,45,-45),V(1,0,0),7).cut(ax(24,rear-8.6,rear-1.4))
    add('CY-06','活塞锁紧螺母_沉入活塞',nut,moving=True,thread='M24x1.5',notes='Recess prevents collision at zero extension; locking method final assembly review.')
    add('CY-07','活塞锁紧垫圈',ringx(36,24.2,rear-1.5,rear-.5),moving=True)
    add('POS-M','内置位移参考磁环',ringx(29,24.2,rear-10,rear-8.55),group='Sensors',material='magnet composite',moving=True,basis='optional nominal magnetostrictive ring; catalogue pending')
    probe=fuse(ax(8,40,238.01),ax(15.9,238,250),hexprism(24,V(250,45,-45),V(1,0,0),8),ax(24,258,280),ax(12,280,290))
    add('POS-01','内置位移参考探杆_校准与开阀后重置',probe,group='Sensors',material='stainless',basis='optional nominal magnetostrictive sensor envelope; catalogue and accuracy pending',thread='M16x1.5; nominal thread envelope',notes='Reference option for bench calibration/rebasing; sensor accuracy is unverified. Blind rod bore provides full 140 mm clearance.')
    for k,(a,b) in enumerate(((front+3.05,front+6.95),(front+22.05,front+25.95)),1):
        band=ringx(62.8,60.6,a,b).cut(box(a-.1,b+.1,44.5,45.5,-14.8,-13.2))
        add('GD-P'+str(k),'活塞分口导向带',band,material='PTFE composite',moving=True)
    # Separate energiser and PTFE cap: installed contact at bore, zero material penetration.
    add('SE-P1','活塞组合密封_PTFE外环',ringx(63,60.8,front+10.05,front+18.95),group='Seals',material='PTFE',moving=True)
    add('SE-P2','活塞组合密封_NBR励磁圈',ellipse_ring(29.45,.94,1.87,front+14.5,V(0,45,-45),V(1,0,0)),group='Seals',material='NBR70',moving=True)
    for i,(y,z) in enumerate([(y,z) for y in(8,82) for z in(-8,-82)],1):
        add('TR-'+str(i),'油缸端盖拉杆',ax(10,-17,267,y,z),group='Fasteners',material='10.9 steel',thread='M10x1.5 two ends; preload to be calculated')
        for end,a in (('F',-2),('R',250)):
            add('TW-'+end+str(i),'拉杆平垫圈',ringx(20,10.5,a,a+2,y,z),group='Fasteners',material='hardened steel')
        for end,a in (('F',-10),('R',252)):
            s=hexprism(17,V(a,y,z),V(1,0,0),8).cut(ax(10,a-.1,a+8.1,y,z))
            add('TN-'+end+str(i),'拉杆六角螺母',s,group='Fasteners',material='class 10 steel',thread='M10x1.5')

def cavity22(x):
    # Manufacturer 2.13-1008, 3-395.4; permitted 180 degree drill bottom is used
    # to retain the wall for the removable throttling insert. Thread is major envelope.
    return fuse(cz(35,61.7,62.01,x),Part.makeCone(11.925,10.25,2.6,V(x,45,62),V(0,0,-1)),
                cz(22,45.5,59.4,x),cz(20.5,33.8,45.51,x),
                Part.makeCone(10.25,9.5,1.353,V(x,45,33.8),V(0,0,-1)),
                cz(19,21.5,32.45,x),cz(18.6,20.5,21.51,x))

def relief_custom(x=122):
    # Existing project M20 interface, explicitly nominal until a purchasable model is selected.
    body=old['cartridge_20'](x)[0]
    return body

def transform(s,rotation,translation):
    s=s.copy();s.Placement=App.Placement(translation,rotation).multiply(s.Placement);return s

def build_block(vendor):
    old['cavity_22']=cavity22
    old['B']['阻尼孔螺塞'].update(Z=[16,20],螺纹孔Z=[15.5,20.5],图示孔径_mm=.1)
    N=old['nets']()
    # Independently measured cavity temperatures support the P3 dual-volume estimator.
    N['R_T2_port']=fuse(cy(5,12,45.01,99,14),cy(10,-.01,12.01,99,14),cy(16,-.01,.3,99,14))
    # Insert a second independent local thermal relief into the C lock volume.
    rot=App.Rotation(V(0,0,1),V(0,1,0))
    placement=App.Placement(V(199,28,21),rot) # old point (122,45,62) mapped below explicitly
    local=old['cavity_20'](122).copy()
    local.translate(V(-122,-45,-62))
    local=transform(local,rot,V(199,90,21))
    N['K_Crelief']=local
    N['C_Crelief_port']=fuse(cy(6,44.9,57.01,199,21),cz(6,13.99,21.01,199,45))
    N['X_Crelief_return']=fuse(cz(5,20.99,62.01,199,70),cz(9.728,50,62.01,199,70),cz(20,61.7,62.01,199,70))
    blk=box(0,250,0,90,0,62).cut(Part.makeCompound(list(N.values()))).removeSplitter()
    add('BL-01','集成阀块_厂家M22阀孔_双腔独立热泄压',blk,group='Block',notes='M22x1.5 per Wandfluh 3-395.4; 180 degree bottom permitted. M20 relief cavities nominal pending procurement.',thread='4xM22x1.5; 2xM20x1.5; G ports; M14x1.5; 4xM8')
    NETS.update(N)
    # Official vendor body includes two solids, both remain manufacturer parts.
    # Coil native front x=0 is aligned to armature shoulder x=-17.2; rear touches nut at -67.2.
    R=App.Rotation(V(1,0,0),V(0,0,-1))
    for key,x in (('V2',24),('V4',74),('V3',176),('V1',226)):
        p=V(x,45,62)
        for i,s in enumerate(vendor['SDSPM22-X5-BA.STEP'].Solids,1):
            add(key+'-BD'+str(i),key+'_厂家座阀与紧固帽',transform(s,R,p),group='Valves',basis='official Wandfluh STEP STP_1.11-2061',notes='Manufacturer solid topology retained; supplier internal functional construction not fully exposed.')
        for i,s in enumerate(vendor['VDE37_19x50.STEP'].Solids,1):
            s=s.copy();s.translate(V(-17.2,0,0))
            # Connector points +Y away from neighbouring valves along X.
            add(key+'-CL'+str(i),key+'_厂家线圈组件_'+str(i),transform(s,R,p),group='Valves',material='vendor multi-material',basis='official Wandfluh VDE37_19x50.STEP')
        for i,s in enumerate(vendor['HB0.STEP'].Solids,1):
            s=s.copy();s.translate(V(-91.1,0,0))
            add(key+'-HB'+str(i),key+'_厂家封闭插头_'+str(i),transform(s,R,p),group='Valves',basis='official Wandfluh HB0.STEP')
        # Installed seal envelopes from published spare-ring sizes, installation assumptions explicit.
        for i,(t,rc,ra,ta,spec) in enumerate(((2.1,11.02,.89,1.975,'18.72x2.62'),(15.7,9.925,.32,2.475,'18.77x1.78'),(33.25,8.77,.72,1.10,'15.60x1.78')),1):
            s=ellipse_ring(rc,ra,ta,t,V(0,0,0),V(1,0,0))
            s=transform(s,R,p).cut(transform(vendor['SDSPM22-X5-BA.STEP'],R,p)).common(cavity22(x)).removeSplitter()
            add(key+'-SE'+str(i),key+'_安装密封包络_'+spec,s,group='Seals',material='NBR70',basis='manufacturer stock ring size; available installed gland envelope only',notes='Occupies available gland space; does not prove compression ratio or sealing performance. Supplier gland confirmation required.')
        backup=cx(19,30.65,32.05,0,0).cut(cx(16.1,30.55,32.15,0,0))
        add(key+'-BR',key+'_厂家尺寸挡圈_16.1x19x1.4',transform(backup,R,p),group='Seals',material='PTFE',basis='manufacturer spare part dimensions; installed position provisional')
    add('RV-R','有杆腔7MPa机械溢流阀_设计包络',relief_custom(),group='Valves',basis='project nominal M20 design envelope, supplier pending',thread='M20x1.5')
    rv=relief_custom();rv.translate(V(-122,-45,-62));rv=transform(rv,rot,V(199,90,21))
    add('RV-C','无杆腔7MPa机械溢流阀_设计包络',rv,group='Valves',basis='project nominal M20 design envelope, supplier pending',thread='M20x1.5')
    s2=B['测压与测温']['第一测压孔_S2']
    add('PS-C','无杆腔压力传感器',old['psensor'](V(176,0,14),V(0,-1,0)),group='Sensors',material='stainless',basis='nominal G1/4 sensor envelope',thread='G1/4 A')
    add('PS-R','有杆腔压力传感器',old['psensor'](V(0,45,14),V(-1,0,0)),group='Sensors',material='stainless',basis='nominal G1/4 sensor envelope',thread='G1/4 A')
    well,probe=old['thermowell']()
    add('TW-01','封闭端油温套管',well,group='Sensors',material='304 stainless',thread='M14x1.5')
    add('PT-01','Pt100油温探杆',probe,group='Sensors',material='stainless',basis='nominal diameter 3 probe envelope')
    rwell=fuse(cy(3,11.99,43.5,99,14),cy(9.9,0,12.01,99,14),hexprism(14,V(99,0,14),V(0,-1,0),6))
    rwell=rwell.cut(cy(2.2,-6.1,42.5,99,14))
    add('TW-R','有杆腔独立封闭测温套管',rwell,group='Sensors',material='304 stainless',thread='M10x1',notes='Independent cavity temperature; closed tip 1mm. Sensor time constant requires bench identification.')
    rprobe=fuse(cy(2,-6,42.4,99,14),cy(12,-26,-6,99,14),cy(8,-36,-26,99,14))
    add('PT-R','有杆腔独立Pt100温度探杆',rprobe,group='Sensors',material='stainless',basis='nominal diameter2 Pt100 probe, catalogue pending')
    for key,x,z in (('R',122,24),('C',224,19)):
        add('TP-'+key,'测压排气接头_'+key,old['coupling'](V(x,0,z),V(0,-1,0)),group='Ports',basis='nominal M16x2 test fitting envelope',thread='M16x2')
    plug=old['orifice_plug']()
    add('OR-01','可换阻尼螺塞_真实孔径0.1',plug,group='Block',material='304 stainless',thread='M8x1 with hydraulic thread seal',notes='Actual 0.1 mm through hole; z16..20; shoulder/thread sealing must be specified for procurement/manufacturing.')
    for no,x in (('R',24),('C',226)):
        add('SE-F'+no,'阀块对接端面O圈_'+no,old['oring_face'](x),group='Seals',material='NBR70',basis='15x2.65 nominal installed compressed')
    for i,(x,y) in enumerate(B['安装与密封']['连接螺栓']['位置'],1):
        add('BS-'+str(i),'阀块连接内六角螺钉',old['bolt'](x,y),group='Fasteners',material='8.8 steel',thread='M8x70, pitch 1.25, engaged length 17')
    for i,(x,y) in enumerate(B['安装与密封']['定位销']['位置'],1):
        add('DP-'+str(i),'端盖阀块定位销',cz(6,-6,9.5,x,y),group='Fasteners',material='hardened steel',notes='Nominal interference/dowel fit represented by equal envelopes.')
    # Every external operational port has a real through-bore fitting.
    # BSPP port-face seal closure remains pending supplier/interface confirmation.
    for name,x,z,thread,td,bore in (('B',30,40,'G3/8',16.662,8),('PP',74,40,'G1/4',13.157,6),('RT',122,44,'G1/4',13.157,5),('T',176,40,'G1/4',13.157,5),('A',220,40,'G3/8',16.662,8)):
        p=V(x,90,z);d=V(0,1,0)
        stem=Part.makeCylinder((td-.12)/2,10,p,-d)
        fitting=fuse(stem,hexprism(22 if td>15 else 19,p,d,10),Part.makeCylinder(10 if td>15 else 8,14,p+d*10,d))
        fitting=fitting.cut(Part.makeCylinder(bore/2,34.2,p-d*10.1,d))
        add('PF-'+name,'外接油口适配接头_'+name,fitting,group='Ports',basis='nominal BSPP straight adapter envelope',thread=thread)
    # C relief drain on top; bore is open into horizontal relief annulus.
    p=V(199,70,62)
    stem=cz(9.60,52,62,199,70)
    fitting=fuse(stem,hexprism(14,p,V(0,0,1),8),cz(6,70,84,199,70)).cut(cz(4,51.9,84.1,199,70))
    add('PF-CT','无杆腔热溢流独立回油接头',fitting,group='Ports',basis='nominal G1/8 adapter',thread='G1/8')

def build(vendor,job):
    PARTS.clear();NETS.clear()
    job['detail']='cylinder, caps, seals and tie rods'
    build_cylinder()
    job['detail']='block networks, official valve assets and external ports'
    build_block(vendor)
    summary=[{k:v for k,v in p.items() if k!='shape'}|{'valid':p['shape'].isValid(),'solids':len(p['shape'].Solids),'volume_mm3':p['shape'].Volume} for p in PARTS]
    return PARTS,NETS,summary
