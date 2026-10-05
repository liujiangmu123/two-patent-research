"""Complete nominal rig assembly, using live MCP-owned core geometry.

Commercial items without selected order codes are tagged nominal envelopes.
Welded subassemblies are separated from standard fasteners and internal parts.
"""
import math
import copy
import FreeCAD as App
import Part
V=App.Vector
P=[]
def box(a,b,c,d,e,f):return Part.makeBox(b-a,d-c,f-e,V(a,c,e))
def cyl(r,p,d,l):return Part.makeCylinder(r,l,V(p),V(d))
def fuse(*ss):
    s=ss[0]
    for t in ss[1:]:s=s.fuse(t)
    return s.removeSplitter()
def add(no,name,s,group,material='steel',basis='nominal custom design',notes='',moving='fixed'):
    if s.isNull() or not s.isValid() or not s.Solids:raise ValueError('Invalid '+no)
    P.append(dict(no=no,name=name,shape=s,group=group,material=material,basis=basis,notes=notes,moving=moving))
def hexp(af,p,d,l):return App._che_core_module.hexprism(af,V(p),V(d),l)
def tube_box(a,b,c,d,e,f,t=4):
    s=box(a,b,c,d,e,f)
    lengths=[b-a,d-c,f-e];axis=lengths.index(max(lengths))
    v=[a,b,c,d,e,f]
    for i in range(3):
        v[2*i]+=(-.1 if i==axis else t);v[2*i+1]+=(.1 if i==axis else -t)
    return s.cut(box(*v))
def prism_xy(points,z0,z1):
    w=Part.makePolygon([V(x,y,z0) for x,y in points]+[V(*points[0],z0)])
    return Part.Face(w).extrude(V(0,0,z1-z0))
def ax(r,a,b,y=500,z=1080):return cyl(r,(a,y,z),(1,0,0),b-a)
def ringx(od,id,a,b):return ax(od/2,a,b).cut(ax(id/2,a-.1,b+.1))
def drill_z(shape,positions,d,z0,z1):return shape.cut(Part.makeCompound([cyl(d/2,(x,y,z0),(0,0,1),z1-z0) for x,y in positions]))
def bolt_z(no,x,y,zseat,length=25,d=8,group='Fasteners'):
    s=fuse(cyl(d/2,(x,y,zseat-length),(0,0,1),length),cyl(d*.81,(x,y,zseat),(0,0,1),d))
    s=s.cut(hexp(d*.75,(x,y,zseat+d*.5),(0,0,1),d*.6))
    add(no,'内六角螺钉_M'+str(d),s,group,basis='nominal standard fastener envelope',notes='Thread pitch and engagement specified in part list.')
def rolling_bearing(no,a,b,od,id,group='Tailstock'):
    outer=ringx(od,od-10,a,b);inner=ringx(id+8,id,a,b)
    add(no+'-O','轴承外圈',outer,group,basis='nominal bearing envelope; final catalogue selection required',moving='piston_x')
    add(no+'-I','轴承内圈',inner,group,basis='nominal bearing envelope',moving='piston_x')
    rad=(od-10+id+8)/4;ballr=(od-10-id-8)/4
    for i in range(12):
        ang=2*math.pi*i/12
        add(no+'-B'+str(i+1),'轴承滚动体',Part.makeSphere(ballr-.05,V((a+b)/2,500+rad*math.cos(ang),1080+rad*math.sin(ang))),group,basis='nominal rolling topology, no rated bearing-life claim',moving='piston_x')
    add(no+'-C','轴承保持架',ringx(od-10-.2,id+8+.2,(a+b)/2-.7,(a+b)/2+.7).cut(Part.makeCompound([Part.makeSphere(ballr+.1,V((a+b)/2,500+rad*math.cos(2*math.pi*i/12),1080+rad*math.sin(2*math.pi*i/12))) for i in range(12)])),group,material='brass',basis='nominal rolling topology')

def refine_chuck():
    """Custom nonrotating 100/25/20 test actuator, not invented rotary-cylinder internals."""
    old={p['no']:p for p in P}
    tie=[(y,z) for y in (450,550) for z in (1030,1130)]
    front=fuse(box(140,170,435,565,1015,1145),ax(54.95,170,175))
    rear=fuse(box(250,300,435,565,1015,1145),ax(54.95,245,250))
    barrel=ringx(130,100,170,250).cut(ax(55,169.9,175)).cut(ax(55,245,250.1))
    for y,z in tie:
        front=front.cut(ax(4.2,139.9,175.1,y,z));rear=rear.cut(ax(4.2,244.9,300.1,y,z))
    rear=rear.cut(ax(12.55,244.9,300.1))
    for a,b,d in ((255,265,30),(270,276,31),(283,289,31),(297,300,33)):
        rear=rear.cut(ax(d/2,a,b))
    for t,a,b in ((172.5,170.7,174.3),(247.5,245.7,249.3)):
        if t<200:front=front.cut(ringx(111,106,a,b))
        else:rear=rear.cut(ringx(111,106,a,b))
        seal=App._che_core_module.ellipse_ring(54,.99,1.76,t,V(0,500,1080),V(1,0,0))
        add('CH-SE-C'+str(int(t)),'卡盘试验缸端盖静密封圈',seal,'Chuck',material='NBR70',basis='nominal installed ring, catalogue compression review pending')
    for name,x in (('C',154),('R',266)):
        # End-face outlets remain open at both hard stops; side ports would be blocked by the piston.
        bore=fuse(cyl(3,(x,500,1119.9),(0,0,1),25.1),cyl(6.5785,(x,500,1134.5),(0,0,1),10.6))
        bore=fuse(bore,ax(3,x,175.01,500,1120) if name=='C' else ax(3,244.99,x,500,1120))
        if name=='C':front=front.cut(bore).cut(cyl(11,(x,500,1144.5),(0,0,1),.6))
        else:rear=rear.cut(bore).cut(cyl(11,(x,500,1144.5),(0,0,1),.6))
        fitting=fuse(cyl(6.51,(x,500,1134.5),(0,0,1),10),hexp(19,(x,500,1144.5),(0,0,1),8),cyl(8,(x,500,1152.5),(0,0,1),14))
        fitting=fitting.cut(cyl(3,(x,500,1134.4),(0,0,1),32.2))
        add('CH-PF'+name,'卡盘试验缸G1/4油口_'+name,fitting,'Chuck',basis='nominal BSPP adapter, bonded sealing review pending')
    old['CH-CYL'].update(shape=barrel,name='卡盘试验缸筒_100H8',basis='custom nominal nonrotating test design 100/25/20',notes='70 mm chamber, piston plus stops50 mm yields20 mm stroke; not a rotary-cylinder catalogue substitute.')
    add('CH-CF','卡盘试验缸前端盖_可拆止口',front,'Chuck')
    add('CH-CR','卡盘试验缸杆端盖_杆封导向槽',rear,'Chuck')
    piston=ringx(99.9,20.2,185.5,234.5).cut(ax(18,185.4,193))
    for a,b,d in ((188.5,193.5,97),(205,215,94),(226.5,231.5,97)):
        piston=piston.cut(ringx(101,d,a,b))
    piston=fuse(piston,ringx(40,34,185,185.51),ringx(40,25.2,234.49,235))
    old['CH-PIS'].update(shape=piston,name='卡盘试验活塞_49宽_密封导向槽',basis='custom nominal100/25/20 test actuator')
    rod=fuse(ax(10,185.45,234.5),ax(12.5,234.5,382),ax(12,382,530))
    old['CH-ROD'].update(shape=rod,name='卡盘试验拉杆_M20活塞_M24加载端',basis='custom nominal rod; nominal threaded envelopes')
    nut=hexp(30,(185.6,500,1080),(1,0,0),7).cut(ax(10,185.5,192.7))
    add('CH-PN','卡盘活塞锁紧螺母_M20x1.5',nut,'Chuck',basis='nominal standard fastener')
    for no,a,b in (('A',188.55,193.45),('B',226.55,231.45)):
        add('CH-GP'+no,'卡盘活塞分口导向带',ringx(99.8,97.1,a,b).cut(box(a-.1,b+.1,499.5,500.5,1127.9,1130.1)),'Chuck',material='PTFE composite')
    add('CH-SP','卡盘活塞组合密封外环',ringx(100,97.8,205.05,214.95),'Chuck',material='PTFE',basis='nominal seal profile, supplier pending')
    add('CH-EP','卡盘活塞密封励磁圈',App._che_core_module.ellipse_ring(47.95,.94,1.87,210,V(0,500,1080),V(1,0,0)),'Chuck',material='NBR70')
    add('CH-GR','卡盘杆端青铜导向套',ringx(29.9,25.1,255.05,264.95),'Chuck',material='CuSn12')
    for no,a,b,od in (('R1',270.05,275.95,30.9),('R2',283.05,288.95,30.9),('W',297.05,299.95,32.9)):
        shape=ringx(od,25,a,b)
        if no!='W':shape=shape.cut(ringx(29.5,26.5,a-.1,b-1))
        add('CH-S'+no,'卡盘杆端密封_'+no,shape,'Chuck',material='PU/NBR',basis='nominal U cup open to chamber, catalogue pending')
    for i,(y,z) in enumerate(tie,1):
        add('CH-TR'+str(i),'卡盘端盖M8拉杆',ax(4,130.9,315,y,z),'Fasteners',basis='nominal 10.9 tie rod')
        for end,a in (('F',138),('R',300)):
            washer=ax(8,a,a+2,y,z).cut(ax(4.25,a-.1,a+2.1,y,z))
            nut=hexp(13,(a-6.5 if end=='F' else a+2,y,z),(1,0,0),6.5)
            nut=nut.cut(ax(4,a-6.6 if end=='F' else a+1.9,a+.1 if end=='F' else a+8.6,y,z))
            add('CH-TW'+end+str(i),'卡盘拉杆平垫圈',washer,'Fasteners',basis='nominal hardened washer')
            add('CH-TN'+end+str(i),'卡盘拉杆M8螺母',nut,'Fasteners',basis='nominal class10 nut')
    # The disc-spring force chain closes into the cylinder rear face, with real shoulders.
    add('CH-RXN','卡盘测力传感器反力隔套',ringx(70,25.2,300,305),'Chuck')
    add('CH-WF','碟簧组前反力垫圈',ringx(50,25.4,330,334),'Chuck')
    add('CH-WR','碟簧组后压紧垫圈',ringx(50,24.4,382,386),'Chuck')
    add('CH-NUT','卡盘碟簧组加载螺母_M24x1.5',hexp(36,(386,500,1080),(1,0,0),14).cut(ax(12,385.9,400.1)),'Chuck',basis='nominal standard thread envelope')
    for p in P:
        if p['no'] in ('CH-PIS','CH-ROD','CH-PN','CH-GPA','CH-GPB','CH-SP','CH-EP','CH-NUT','CH-WR'):
            p['moving']='chuck_rod_x'

def build(core,job):
    P.clear()
    job['detail']='frame and bed'
    # Actual hollow steel sections, weld interfaces have no overlapping solid volumes.
    for i,(x,y) in enumerate([(x,y) for x in (0,870,1740) for y in (0,740)],1):
        add('FR-L'+str(i),'60x60x4方管立柱',tube_box(x,x+60,y,y+60,0,790),'Frame',material='Q235B')
        foot=fuse(cyl(12,(x+30,y+30,-25),(0,0,1),25),cyl(30,(x+30,y+30,-40),(0,0,1),15))
        add('FR-F'+str(i),'M24可调机脚_底垫',foot,'Frame',basis='nominal standard adjustable foot')
    for no,a,b,c,d,e,f in (('FR-B1',0,1800,0,60,790,850),('FR-B2',0,1800,740,800,790,850),('FR-B3',0,60,60,740,790,850),('FR-B4',1740,1800,60,740,790,850),('FR-B5',870,930,60,740,790,850),('FR-B6',60,870,0,60,100,150),('FR-B7',930,1740,0,60,100,150),('FR-B8',60,870,740,800,100,150),('FR-B9',930,1740,740,800,100,150)):
        add(no,'机架横梁_空心方管',tube_box(a,b,c,d,e,f),'Frame',material='Q235B')
    add('FR-S','底层设备搁板',box(60,1740,60,740,150,158),'Frame',material='Q235B')
    tableholes=[(x,y) for x in (100,500,900,1300,1700) for y in (100,700)]
    table=drill_z(box(0,1800,0,860,850,870),tableholes,8.5,849.9,870.1)
    # Bed mounting holes tapped into table, table itself is welded/bolted to frame.
    bedholes=[(x,y) for x in (260,600,1000,1400,1600) for y in (390,610)]
    table=drill_z(table,bedholes,10,855,870.1)
    add('FR-T','台面_厚20_设备安装孔',table,'Frame',material='Q235B')
    bed=fuse(box(200,1670,380,620,870,915),box(200,1670,400,600,915,930))
    bed=drill_z(bed,bedholes,10.5,869.9,930.1)
    add('BD-01','模拟床身_台阶安装面',bed,'Bed',material='Q235B',notes='Load-bearing bed; fixture tap locations are generated from attached assemblies.')
    for i,(x,y) in enumerate(bedholes,1):bolt_z('BD-S'+str(i),x,y,915,55,d=10)
    job['detail']='rolling wedge and screw drive'
    base=box(595,745,420,650,930,960)
    baseholes=[(x,y) for x in (610,730) for y in (430,640)]
    base=drill_z(base,baseholes,10.5,929.9,960.1)
    base=base.cut(box(630,680,419.9,650.1,929.9,960.1))
    wall=box(600,640,440,620,960,1135)
    add('LD-01','加载底板',base,'Loader')
    add('LD-02','加载反力挡壁_磨削面',wall,'Loader',material='40Cr hardened')
    for i,(x,y) in enumerate(baseholes,1):bolt_z('LD-S'+str(i),x,y,960,45,d=10)
    wedge=prism_xy([(643,430),(643,630),(693,630),(673,430)],970,1120)
    add('WD-01','1比10楔块_两面滚针接触',wedge,'Loader',material='40Cr HRC58',moving='wedge_y')
    shift=3*math.sqrt(1.01)
    follower=prism_xy([(673+1+shift,440),(735,440),(735,620),(673+19+shift,620)],970,1120)
    follower=follower.cut(ax(12.1,729.9,735.1))
    add('WD-02','从动楔座',follower,'Loader',material='40Cr HRC58',moving='slider_x')
    # Each surface has four rows of seven 3x35 nominal needles, reducing Hertz load.
    for side in ('BACK','FRONT'):
        for row,z in enumerate((975,1010,1045,1080),1):
            for k,y in enumerate((455,475,495,515,535,555,575),1):
                x=641.5 if side=='BACK' else 673+.1*(y-430)+1.5*math.sqrt(1.01)
                add('ND-'+side+str(row)+'-'+str(k),'楔面滚针_3x30',cyl(1.5,(x,y,z),(0,0,1),30),'Loader',material='GCr15',basis='nominal rolling contact geometry',moving='needle_cage')
    # Screw and nut sit below wedge; no geometric pass through the inclined rollers.
    screw=fuse(cyl(8,(655,420,945),(0,1,0),210),cyl(6,(655,390,945),(0,1,0),30),cyl(6,(655,630,945),(0,1,0),45))
    add('SC-01','滚珠丝杠_16_导程5_有效行程20',screw,'Loader',basis='nominal C5 ball-screw envelope',notes='No claimed helix/race contact rating before procurement.')
    nut=fuse(cyl(14,(655,510,945),(0,1,0),40),box(635,675,515,525,935,955)).cut(cyl(8.1,(655,509.9,945),(0,1,0),40.2))
    add('SC-02','滚珠丝杠螺母_法兰',nut,'Loader',basis='nominal catalogue-independent nut',moving='wedge_y')
    bridge=box(647,663,510,550,959,970)
    add('SC-03','螺母与楔块连接桥',bridge,'Loader',moving='wedge_y')
    for end,y in (('F',390),('R',630)):
        housing=box(635,675,y,y+30,930,965).cut(cyl(14,(655,y-.1,945),(0,1,0),30.2))
        bearing=cyl(14,(655,y+.2,945),(0,1,0),29.6).cut(cyl(6.1,(655,y+.1,945),(0,1,0),29.8))
        add('SC-SP'+end,'丝杠支撑座',housing,'Loader',basis='nominal support housing')
        add('SC-BR'+end,'丝杠支撑轴承总成',bearing,'Loader',basis='nominal integrated bearing envelope; supplier details pending')
    coupling=cyl(16,(655,660,945),(0,1,0),30).cut(cyl(6.1,(655,659.9,945),(0,1,0),30.2))
    add('SV-CP','伺服联轴器',coupling,'Loader',basis='nominal flexible coupling envelope')
    servo=fuse(box(615,695,690,705,905,985),box(620,690,705,765,910,980),cyl(6,(655,675,945),(0,1,0),15))
    add('SV-01','750W带抱闸伺服电机',servo,'Loader',basis='nominal servo envelope; 2.39 Nm rated assumption')
    mount=box(600,710,680,690,870,990).cut(cyl(20,(655,679.9,945),(0,1,0),10.2))
    add('SV-02','伺服电机支架',mount,'Loader')
    # Two x rails; rail screw holes and carriage screw holes are real cut geometry.
    for i,y in enumerate((455,535),1):
        rail=box(758,970,y-10,y+10,930,948)
        holes=[(x,y) for x in (785,835,885,935)]
        rail=drill_z(rail,holes,5.5,929.9,948.1)
        rail=drill_z(rail,holes,9,942,948.1)
        add('LR-'+str(i),'滑块直线导轨_20',rail,'Loader',basis='nominal preloaded linear rail envelope')
        for j,(x,yy) in enumerate(holes,1):bolt_z('LR-S'+str(i)+'-'+str(j),x,yy,942,20,d=5)
        for j,x in enumerate((778,845),1):
            carriage=box(x,x+45,y-17,y+17,943,965).cut(box(x-.1,x+45.1,y-10.1,y+10.1,942.9,948.1))
            holes=[(x+10,y-11),(x+35,y+11)]
            carriage=drill_z(carriage,holes,5,954,965.1)
            add('LC-'+str(i)+'-'+str(j),'导轨预紧滑块',carriage,'Loader',basis='nominal guide carriage envelope',moving='slider_x')
    sensor=fuse(ax(28,735,765),ax(12,730,735),ax(12,765,770))
    sensor=sensor.cut(ax(4,734.9,765.1,500,1094))
    add('FS-L','加载端20kN轴向测力传感器',sensor,'Sensors',basis='nominal force cell envelope and assumed axial stiffness',moving='slider_x')
    # Zero-gap 60 degree centre interface, matching female taper cut at x880.
    slider=fuse(box(770,902,440,560,965,982),box(770,902,480.1,519.9,982,1120))
    taper=Part.makeCone(0,22*math.tan(math.pi/6),22,V(880,500,1080),V(1,0,0))
    slider=slider.cut(taper).cut(ax(12.1,769.9,781))
    add('WS-01','工件模拟滑块_60度中心孔',slider,'Loader',moving='slider_x')
    for i,y in enumerate((455,535),1):
        for j,x in enumerate((778,845),1):
            for k,(xx,yy) in enumerate(((x+10,y-11),(x+35,y+11)),1):
                # Drilled slider bores are added in one finish pass below.
                bolt_z('WS-S'+str(i)+str(j)+str(k),xx,yy,978,23,d=5)
    ws=next(p for p in P if p['no']=='WS-01')
    wsholes=[(x+10,y-11) for y in (455,535) for x in (778,845)]+[(x+35,y+11) for y in (455,535) for x in (778,845)]
    ws['shape']=drill_z(ws['shape'],wsholes,5.5,964.9,978.1)
    ws['shape']=drill_z(ws['shape'],wsholes,9,978,982.1)
    # LVDT directly references slider, independent of screw encoder and wedge compliance.
    lvdt=fuse(ax(10,940,1045,420,1110),ax(2,902,940,420,1110))
    add('DS-01','滑块独立LVDT_量程正负1mm',lvdt,'Sensors',basis='nominal sensor envelope, resolution .5 um target')
    bracket=box(1045,1060,405,435,930,1125).cut(ax(10,1044.9,1060.1,420,1110))
    add('DS-02','位移传感器支架',bracket,'Sensors')
    job['detail']='tailstock, floating cylinder fixture and thermal jacket'
    tip=Part.makeCone(0,20,20/math.tan(math.pi/6),V(880,500,1080),V(1,0,0))
    tip=fuse(tip,ax(15,880+20/math.tan(math.pi/6),1005))
    add('TS-TIP','回转顶尖_60度_轴承支承芯轴',tip,'Tailstock',material='GCr15',moving='piston_x')
    quill=ringx(75,35,920,1290)
    for a,b in ((944,960),(984,1000)):quill=quill.cut(ax(31.05,a,b))
    quill=quill.cut(ax(21,1205,1290.1))
    add('TS-QUILL','尾座套筒_轴承台阶与后端连接',quill,'Tailstock',moving='piston_x')
    rolling_bearing('TS-B1',944,960,62,30)
    rolling_bearing('TS-B2',984,1000,62,30)
    add('TS-CAP','顶尖前端轴承挡圈',ringx(75,30.2,915,920),'Tailstock',moving='piston_x')
    housing=fuse(box(1120,1320,400,600,930,960),box(1130,1310,430,570,960,1150))
    housing=housing.cut(ax(37.6,1119.9,1320.1))
    housing=housing.cut(ax(14.5,1280,1320.1,500,1139))
    add('TS-HOUSE','尾座导向体_可更换导向衬套',housing,'Tailstock')
    add('TS-G1','套筒前导向衬套',ringx(75.2,75.05,1130,1170),'Tailstock',material='bronze')
    add('TS-G2','套筒后导向衬套',ringx(75.2,75.05,1175,1215),'Tailstock',material='bronze')
    # Split support is intentionally free axially for measured cylinder reaction.
    for p in core:
        s=p['shape'].copy();s.translate(V(1365,455,1125))
        add('TC-'+p['no'],p['name'],s,'TailHydraulics',p['material'],p['basis'],p['notes'],moving='piston_x' if p['moving'] else 'floating_cylinder')
    conn=fuse(ringx(40,24,1205,1285),ringx(35,24,1190,1205))
    add('TS-LINK','套筒活塞杆螺纹连接套',conn,'Tailstock',notes='M24x1.5 nominal thread envelope; axial gap zero at quill rear face.',moving='piston_x')
    # Floating sled beneath cylinder, support rails allow small axial sensing motion.
    for i,y in enumerate((475,525),1):
        add('FC-LR'+str(i),'浮动缸座导轨',box(1340,1590,y-8,y+8,930,946),'FloatingFixture',basis='nominal low-friction rail')
        for j,x in enumerate((1370,1500),1):
            carriage=box(x,x+45,y-15,y+15,940,960).cut(box(x-.1,x+45.1,y-8.1,y+8.1,939.9,946.1))
            add('FC-LC'+str(i)+str(j),'浮动缸座滑块',carriage,'FloatingFixture',basis='nominal linear carriage',moving='floating_cylinder')
    sled=box(1340,1570,450,550,960,1025)
    add('FC-SLED','油缸浮动安装座',sled,'FloatingFixture',moving='floating_cylinder',notes='Top 1025 equals cylinder bottom1035 minus10 thermal jacket; mounting interface to jacket/support review.')
    react=fuse(ringx(80,45,1580,1610),ringx(55,45,1610,1620))
    for yy,zz in ((467.5,1080),(532.5,1080),(500,1112.5),(500,1047.5)):
        react=react.cut(ax(3.2,1579.9,1610.1,yy,zz))
    add('FS-R','浮动缸座环形轴向反力传感器_20kN',react,'Sensors',basis='nominal annular reaction-cell envelope; catalogue pending',notes='45 mm clear centre admits optional axial position-reference probe.')
    add('FC-STOP','反力传感器后支座',box(1620,1632,450,550,930,1125).cut(ax(22.6,1619.9,1632.1)),'FloatingFixture',notes='45.2 mm bore clears position probe; annular 55 mm rear sensor face seats at x1655 after translation.')
    # U shaped solid jacket with closed water passages, split covers and gasket bodies.
    outer=box(1364,1536,443,557,1025,1124.5)
    inner=box(1363.9,1536.1,455,545,1035,1124.6)
    jacket=outer.cut(inner)
    channels=[]
    # Flow traverses left wall, bottom and right wall; all grooves intersect and terminate at hose ports.
    for x in (1380,1410,1440,1470,1500,1520):
        channels.append(cyl(3,(x,449,1040),(0,0,1),84.6))
        channels.append(cyl(3,(x,551,1040),(0,0,1),84.6))
    channels += [cyl(3,(1380,449,1040),(1,0,0),140),cyl(3,(1380,551,1110),(1,0,0),140),cyl(3,(1520,449,1040),(0,1,0),102),cyl(3,(1380,449,1110),(1,0,0),140)]
    jacket=jacket.cut(Part.makeCompound(channels))
    add('TJ-01','温控U形夹套_真实内水道',jacket,'Thermal',material='6061-T6',notes='Drilled channel closures listed individually; coolant 4 L/min assumption.',moving='floating_cylinder')
    for side,y in (('L',443),('R',557)):
        for i,x in enumerate((1380,1410,1440,1470,1500,1520),1):
            # Vertical drill access is sealed at top with nominal threaded plugs, leaving no open water inlet.
            plug=cyl(2.95,(x,449 if side=='L' else 551,1118.5),(0,0,1),6)
            add('TJ-PL'+side+str(i),'夹套工艺孔封堵螺塞',plug,'Thermal',basis='nominal threaded hydraulic plug',moving='floating_cylinder')
    # Hydraulic power unit: welded tank wall, service cover, pump/motor with interface flanges.
    job['detail']='power unit, chuck simulator and guard'
    tank=box(70,450,80,420,158,420).cut(box(76,444,86,414,164,420.1))
    add('HP-TANK','液压站油箱_空腔与壁厚6',tank,'Power',material='Q235B')
    cover=box(70,450,80,420,420,428)
    add('HP-COVER','油箱检修顶盖',cover,'Power')
    add('HP-PUMP','5.8Lmin齿轮泵_1.1kW电机接口',fuse(box(165,235,190,280,430,495),cyl(14,(200,260,495),(0,0,1),20)),'Power',basis='nominal pump envelope')
    motor=fuse(cyl(65,(200,260,565),(0,0,1),140),box(140,260,230,290,540,565),cyl(14,(200,260,515),(0,0,1),50))
    add('HP-MOTOR','1.1kW泵电机',motor,'Power',basis='nominal motor envelope')
    add('HP-COUP','泵电机联轴器与护罩',cyl(35,(200,260,495),(0,0,1),45).cut(cyl(14.1,(200,260,494.9),(0,0,1),45.2)),'Power',basis='nominal drive coupling')
    acc=fuse(cyl(60,(390,150,450),(0,0,1),150),Part.makeSphere(60,V(390,150,600)).common(box(329.9,450.1,89.9,210.1,450,660)),cyl(12,(390,150,428),(0,0,1),22))
    add('HP-ACC','蓄能器_5至6MPa供压',acc,'Power',basis='nominal rated vessel external envelope; no fabricated bladder internals')
    add('HP-FILTER','回油过滤器_10um名义',cyl(35,(300,340,428),(0,0,1),150),'Power',basis='nominal filter housing; micron rating not geometric pores')
    # Non-rotating chuck-pressure test cylinder and spring elastic-load simulator.
    chuckbody=fuse(ax(65,150,290),ax(55,140,150),ax(55,290,300)).cut(ax(40,160,280)).cut(ax(12.6,279.9,300.1))
    add('CH-CYL','卡盘试验缸_双腔与拉杆孔',chuckbody,'Chuck',basis='nominal chuck test cylinder; rotary purchase selection pending')
    add('CH-PIS','卡盘缸活塞',ringx(79.9,25,245,260),'Chuck')
    add('CH-ROD','卡盘模拟拉杆',ax(12.5,245,530),'Chuck')
    support=fuse(box(160,280,440,560,930,960),box(180,260,460,540,960,1015))
    add('CH-SUP','卡盘缸安装座',support,'Chuck')
    add('CH-FS','50kN穿心夹紧测力传感器',ringx(70,25.2,305,330),'Sensors',basis='nominal annular force-cell envelope')
    # 12 separate conical disc springs, 3 opposed x4 stacks.
    for i in range(12):
        a=334+i*4
        if i%2:profile=[(12.7,a),(25,a+1),(25,a+4),(12.7,a+3)]
        else:profile=[(12.7,a+1),(25,a),(25,a+3),(12.7,a+4)]
        s=App._che_core_module.revolve(profile,V(0,500,1080),V(1,0,0))
        add('CH-DS'+str(i+1),'碟簧_50x25.4x3',s,'Chuck',material='50CrVA',basis='nominal A series disc spring; force curve requires supplier validation')
    spindle=box(400,520,400,600,930,1180).cut(ax(13,399.9,520.1))
    add('CH-SPINDLE','卡盘主轴模拟座',spindle,'Chuck')
    chuck=ringx(200,26,520,565)
    for i,angle in enumerate((90,210,330),1):
        j=box(565,590,-10,10,30,92);j.rotate(V(0,0,0),V(1,0,0),angle-90);j.translate(V(0,500,1080))
        add('CH-J'+str(i),'卡盘径向滑动卡爪',j,'Chuck',basis='nominal non-rotating chuck jaw')
        slot=box(540,565.1,-10.2,10.2,25,94);slot.rotate(V(0,0,0),V(1,0,0),angle-90);slot.translate(V(0,500,1080));chuck=chuck.cut(slot)
    add('CH-BODY','模拟三爪卡盘_导向槽',chuck,'Chuck',basis='nominal chuck fixture body')
    valve=fuse(box(350,390,350,390,1180,1205),cyl(6,(370,370,1205),(0,0,1),25),cyl(15,(370,370,1230),(0,0,1),7))
    add('NV-01','回转泄漏模拟针阀',valve,'Chuck',basis='nominal 0..1 L/min leakage valve envelope')
    # Cabinet is hollow; control panel, switches and doors are individual parts.
    cab=box(0,270,0,250,870,1210).cut(box(6,264,6,244,876,1204))
    cab=cab.cut(box(30,240,-.1,6.1,1050,1160))
    add('EC-BOX','电控柜_门窗与壁厚6',cab,'Controls',material='steel sheet')
    add('EC-HMI','控制触摸屏',box(30,240,-12,0,1050,1160),'Controls',basis='nominal HMI envelope')
    for no,x,y,z in (('ESTOP-1',255,100,1220),('ESTOP-2',50,50,1220)):
        add(no,'急停蘑菇按钮',fuse(cyl(10,(x,y,z-10),(0,0,1),10),cyl(18,(x,y,z),(0,0,1),12)),'Controls',material='polymer',basis='nominal safety switch envelope')
    # All transparent panels are present. Door rails and latching/interlock parts are real objects.
    for i,(x,y) in enumerate([(x,y) for x in (100,1670) for y in (320,765)],1):
        add('GD-P'+str(i),'防护罩30方管立柱',tube_box(x,x+30,y,y+30,870,1330,2),'Guard',material='aluminium')
    for no,a,b,c,d in (('GD-T1',100,1700,320,350),('GD-T2',100,1700,765,795),('GD-T3',100,130,350,765),('GD-T4',1670,1700,350,765)):
        add(no,'防护罩顶部横梁',tube_box(a,b,c,d,1330,1360,2),'Guard',material='aluminium')
    for no,a,b,c,d,e,f in (('GD-BACK',130,1670,789,795,900,1330),('GD-LEFT',124,130,350,765,900,1330),('GD-RIGHT',1670,1676,350,765,900,1330),('GD-TOP',130,1670,350,765,1330,1336)):
        add(no,'聚碳酸酯防护板_6',box(a,b,c,d,e,f),'Guard',material='PC',notes='Protective effectiveness untested; guarding needs machine risk assessment.')
    add('GD-DOOR1','左侧滑动透明门',box(130,1020,310,316,900,1330),'Guard',material='PC',moving='door_x')
    add('GD-DOOR2','右侧滑动透明门',box(1021,1670,310,316,900,1330),'Guard',material='PC',moving='door_x')
    for no,a,b,c,d,e,f in (('GD-RAIL1',100,1700,300,310,1330,1360),('GD-RAIL2',100,1700,300,310,870,890)):
        add(no,'防护门滑轨',box(a,b,c,d,e,f),'Guard',material='aluminium')
    for i,x in enumerate((985,1035),1):
        add('GD-H'+str(i),'门把手',fuse(cyl(5,(x,288,1050),(0,0,1),100),cyl(5,(x,288,1050),(0,1,0),22),cyl(5,(x,288,1150),(0,1,0),22)),'Guard',material='polymer')
    add('GD-LOCK','安全门联锁开关',box(980,1010,280,310,1260,1305),'Controls',basis='nominal interlock envelope; circuit validation required')
    job['detail']='100/25/20 chuck actuator and spring reaction chain'
    refine_chuck()
    job['detail']='fixture hole finishing'
    for p in P:
        if p['group'] in ('Thermal','FloatingFixture') or p['no']=='FS-R':
            p['shape'].translate(V(35,0,0))
    for i,(yy,zz) in enumerate(((467.5,1080),(532.5,1080),(500,1112.5),(500,1047.5)),1):
        screw=fuse(ax(3,1603,1645,yy,zz),ax(4.8,1645,1651,yy,zz))
        screw=screw.cut(hexp(5,(1651.1,yy,zz),(-1,0,0),3.1))
        add('FS-R-S'+str(i),'M6x42环形反力传感器安装螺钉',screw,'Fasteners',basis='nominal standard thread envelope',notes='12 mm rear-cap engagement; head clearance to sensor rear stub .2 mm.',moving='floating_cylinder')
    # Make mating holes in structural supports for all listed bolts, using the same centres.
    bedobj=next(p for p in P if p['no']=='BD-01')
    # Base fasteners close the actual reaction chain into the bed.
    for no,holes,seat,length in (
        ('TS-HOUSE',[(x,y) for x in (1140,1300) for y in (410,590)],960,45),
        ('CH-SUP',[(x,y) for x in (175,265) for y in (450,550)],960,45)):
        obj=next(p for p in P if p['no']==no)
        obj['shape']=drill_z(obj['shape'],holes,10.5,929.9,960.1)
        bedobj['shape']=drill_z(bedobj['shape'],holes,10,910,930.1)
        for i,(x,y) in enumerate(holes,1):bolt_z(no+'-S'+str(i),x,y,seat,length,d=10)
    # Four bottom mounting screws engage the same real holes in the two cylinder caps.
    for i,x in enumerate((1375,1607),1):
        foot=box(x-10,x+(8 if i==2 else 10),455,545,1025,1035)
        holes=[(x,473),(x,527)]
        foot=drill_z(foot,holes,9,1024.9,1035.1)
        add('FC-FOOT'+str(i),'端盖底面支撑垫块',foot,'FloatingFixture',moving='floating_cylinder')
        sledobj=next(p for p in P if p['no']=='FC-SLED')
        sledobj['shape']=drill_z(sledobj['shape'],holes,9,959.9,1025.1)
        for j,(xx,yy) in enumerate(holes,1):
            washer=cyl(8,(xx,yy,957),(0,0,1),3).cut(cyl(4.2,(xx,yy,956.9),(0,0,1),3.2))
            add('FC-W'+str(i)+str(j),'端盖安装平垫圈',washer,'Fasteners',basis='nominal washer',moving='floating_cylinder')
            screw=fuse(cyl(4,(xx,yy,957),(0,0,1),95),cyl(6.5,(xx,yy,949),(0,0,1),8))
            screw=screw.cut(hexp(6,(xx,yy,948.9),(0,0,1),4.1))
            add('FC-S'+str(i)+str(j),'M8x95油缸安装螺钉',screw,'Fasteners',basis='nominal standard thread envelope',notes='17 mm cap engagement through 65 mm sled,10 mm spacer,3 mm washer.',moving='floating_cylinder')
    bedobj['shape']=drill_z(bedobj['shape'],baseholes,10,910,930.1)
    railholes=[(x,y) for y in (455,535) for x in (785,835,885,935)]
    bedobj['shape']=drill_z(bedobj['shape'],railholes,5,919,930.1)
    summary=[{k:v for k,v in p.items() if k!='shape'}|{'valid':p['shape'].isValid(),'solids':len(p['shape'].Solids),'volume_mm3':p['shape'].Volume} for p in P]
    return P,summary
