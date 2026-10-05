# FreeCAD 1.1 freecadcmd 无界面：塔材夹持式双向三面角反射器（无立杆、无GNSS）
import FreeCAD as App, Part, json, os, math
from FreeCAD import Vector as V, Rotation as R, Placement as P
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"..","模型"); os.makedirs(OUT,exist_ok=True)
A=700.0; T=4.0; LB=125.0; LT=10.0   # 反射器内边长 a，板厚；主材 L125x10
doc=App.newDocument("CR_Clamp")
parts={}
def add(name,shape,num,label):
    o=doc.addObject("Part::Feature",name); o.Shape=shape; parts[name]=(o,num,label); return o
# 1 角钢主材段（局部坐标：棱线沿Z，两肢沿+X、+Y）
ang=Part.makeBox(LB,LT,1200).fuse(Part.makeBox(LT,LB,1200)).removeSplitter()
add("AngleMember",ang,1,"角钢主材（非本装置）")
# 2/3 内外夹板：外夹板L形包络角钢外侧（-X,-Y侧为背面），此处角钢背面在 x<0? 角钢棱在原点外侧
outer=Part.makeBox(LB+20,12,260,V(-10,-12,470)).fuse(Part.makeBox(12,LB+20,260,V(-12,-10,470))).removeSplitter()
add("OuterJaw",outer,2,"外夹块（L形，贴合角钢背面）")
inner1=Part.makeBox(LB-30,12,260,V(LT+15,LT,470)); inner2=Part.makeBox(12,LB-30,260,V(LT,LT+15,470))
add("InnerJaw",inner1.fuse(inner2),3,"内压板（两肢各一）")
# 4 夹紧螺栓 4xM16（穿肢不打孔：螺栓位于肢外缘外侧，经U形卡箍）
bolts=None
for z in (510,690):
    for (p,d) in ((V(LB+18,-20,z),V(0,1,0)),(V(-20,LB+18,z),V(1,0,0))):
        b=Part.makeCylinder(8,LT+60,p,d)
        bolts=b if bolts is None else bolts.fuse(b)
add("ClampBolts",bolts,4,"夹紧螺栓 M16×4（不在塔材上钻孔）")
# 5 防滑垫（橡胶-铝复合，兼作电偶隔离）
add("Pad",Part.makeBox(LB,2,240,V(0,-2,480)).fuse(Part.makeBox(2,LB,240,V(-2,0,480))),5,"防滑绝缘垫")
# 6 悬臂托架（沿角钢外分角线方向外伸）
dirv=V(-1,-1,0).normalize()
arm=Part.makeBox(60,60,350,V(-30,-30,0)); arm.rotate(V(0,0,0),V(0,1,0),90); arm.rotate(V(0,0,0),V(0,0,1),225)
arm.translate(V(-12,-12,600))
add("Bracket",arm,6,"悬臂托架")
tip=V(-12,-12,600)+dirv*350
# 7 方位转台
turn=Part.makeCylinder(80,30,tip+V(0,0,30))
add("AzimuthTable",turn,7,"方位转台（刻度盘+锁紧）")
# 8 基准球（夹持基准，几何相位中心相对其已知）
ref=Part.makeSphere(15,V(-12-25,-12-25,760))
add("RefSphere",ref,8,"夹持基准球（相对相位中心偏置已标定）")
# 9 横梁 + 两个俯仰铰
beam=Part.makeBox(900,50,50,tip+V(-450,-25,60))
add("Crossbeam",beam,9,"双向横梁")
cr_info=[]
def trihedral(origin,az,el,tag,numbase):
    # 局部：顶点在原点，三板沿 x,y,z 正向；视轴 (1,1,1)/√3
    p1=Part.Face(Part.makePolygon([V(0,0,0),V(A,0,0),V(0,A,0),V(0,0,0)])).extrude(V(0,0,-T))
    p2=Part.Face(Part.makePolygon([V(0,0,0),V(A,0,0),V(0,0,A),V(0,0,0)])).extrude(V(0,-T,0))
    p3=Part.Face(Part.makePolygon([V(0,0,0),V(0,A,0),V(0,0,A),V(0,0,0)])).extrude(V(-T,0,0))
    # 排水孔 Φ20 位于底板顶点附近
    hole=Part.makeCylinder(10,3*T,V(60,60,-2*T))
    p1=p1.cut(hole)
    # 防覆冰：板背加强筋+ 背面疏冰涂层（标记）；挡雪檐不需（开口朝下倾）
    rib=Part.makeBox(20,20,A*0.6,V(-T-20,-T-20,0))
    sh=p1.fuse([p2,p3,rib]).removeSplitter()
    # 先使视轴对准 +X 后按俯仰、方位旋转
    axis=V(1,1,1).normalize()
    rot0=R(axis,V(1,0,0))
    rot=R(V(0,0,1),az).multiply(R(V(0,1,0),-el)).multiply(rot0)
    sh.Placement=P(origin,rot)
    o=add("CR_"+tag,sh,numbase,"三面角反射器（%s）"%tag)
    bore=rot.multVec(axis)
    return {"tag":tag,"apex":[origin.x,origin.y,origin.z],"boresight":[round(bore.x,4),round(bore.y,4),round(bore.z,4)],"az_deg":az,"el_deg":el}
# 升轨卫星视向：Sentinel-1 升轨 LOS 方位约 东偏~80°(朝西看)，反射器朝向卫星；降轨朝东。入射角 ~39°→ 视轴仰角 51°；取局部坐标 X=东
asc=trihedral(tip+V(-380,0,140),180-10,51-35.26+35.26,"升轨",10)   # el: 视轴仰角
dsc=trihedral(tip+V(380,0,140),10,51,"降轨",11)
cr_info=[asc,dsc]
hinge=None
for x in (-380,380):
    h=Part.makeCylinder(20,80,tip+V(x,-40,110),V(0,1,0))
    hinge=h if hinge is None else hinge.fuse(h)
add("ElevHinge",hinge,12,"俯仰铰（弧形槽+锁紧）")
doc.recompute()
fc=os.path.join(OUT,"塔材夹持式双向三面角反射器.FCStd"); doc.saveAs(fc)
st=os.path.join(OUT,"塔材夹持式双向三面角反射器.step")
Part.export([p[0] for p in parts.values()],st)
# 输出投影用离散边
edges={}
for n,(o,num,lab) in parts.items():
    pl=[]
    for e in o.Shape.Edges:
        try: pts=e.discretize(Number=24)
        except Exception: continue
        pl.append([[round(p.x,1),round(p.y,1),round(p.z,1)] for p in pts])
    edges[n]={"num":num,"label":lab,"edges":pl,"vol_mm3":round(o.Shape.Volume,0)}
json.dump(edges,open(os.path.join(OUT,"edges.json"),"w",encoding="utf-8"),ensure_ascii=False)
rec={"freecad":App.Version()[:3],"files":[fc,st],"params":{"a_mm":A,"t_mm":T,"angle":"L%dx%d"%(LB,LT)},
 "parts":{n:{"num":v[1],"label":v[2],"volume_mm3":round(v[0].Shape.Volume,0),"valid":v[0].Shape.isValid()} for n,v in parts.items()},
 "reflectors":cr_info,"note":"夹持基准球8中心与两反射器顶点（相位中心）偏置由模型给出，安装后以全站仪/激光扫描复核"}
for c in cr_info:
    c["offset_from_ref_mm"]=[round(c["apex"][i]-[-37,-37,760][i],1) for i in range(3)]
json.dump(rec,open(os.path.join(HERE,"..","构建记录.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("OK",[ (n,v["valid"]) for n,v in rec["parts"].items()])
