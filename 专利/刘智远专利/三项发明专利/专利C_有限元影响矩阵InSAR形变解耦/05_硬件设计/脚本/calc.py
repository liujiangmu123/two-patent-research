# 校核计算：RCS、重量、风载、覆冰、夹持安全系数、电气安全距离
import math, json, os
c=299792458.0
bands={"C(Sentinel-1,5.405GHz)":5.405e9,"X(9.65GHz)":9.65e9}
res={"rcs":[]}
for a in [0.4,0.5,0.6,0.7,0.8,1.0]:
    row={"a_m":a}
    for k,f in bands.items():
        lam=c/f; s=4*math.pi*a**4/(3*lam**2)
        row[k]={"lambda_m":round(lam,5),"sigma_m2":round(s,1),"sigma_dBsm":round(10*math.log10(s),1)}
    res["rcs"].append(row)
# 选型：a=0.7 m（C波段≥30 dBsm，SCR>30 dB @ 杂波 -?）
a=0.7; t=0.004; rho=2700  # 5052铝板4 mm
plate_area=a*a/2  # 等腰直角三角形板
m_plate=plate_area*t*rho*3
m_rib=1.6; m_bracket=6.5; m_clamp=7.8; m_hw=1.2
m_cr=m_plate+m_rib
m_total=2*m_cr+m_bracket+m_clamp+m_hw
res["mass"]={"plates_per_CR_kg":round(m_plate,2),"CR_kg":round(m_cr,2),"total_kg":round(m_total,2)}
# 风载：GB50009 w=βz·μs·μz·w0；按设计风速 35 m/s（w0=0.77kPa），高度60 m μz=1.77(B类)，μs=1.3，βz=1.6
w0=0.5*1.25*35**2/1000; muz=1.77; mus=1.3; bz=1.6
A_proj=2*(math.sqrt(3)/2*a*a/ math.sqrt(2)*0.82)  # 两只反射器开口投影面积估算
wk=bz*mus*muz*w0; F=wk*A_proj
ice_t=0.015; ice_rho=900; m_ice=ice_t*plate_area*3*2*ice_rho*0.5  # 排水孔+倾角下按50%挂冰
arm=0.45
M=F*arm
res["wind"]={"w0_kPa":round(w0,3),"wk_kPa":round(wk,3),"A_m2":round(A_proj,3),"F_N":round(F*1000,0),"M_Nm":round(M*1000,0)}
res["ice"]={"t_mm":15,"m_ice_kg":round(m_ice,1)}
# 夹持：4×M16 8.8级，预紧力 Fp=0.7*fy*As? 取 GB50017 P=80kN；摩擦面μ=0.30(防滑垫+喷砂)，2个摩擦面
P=80.0; n=4; mu=0.30; nf=2
Fslip=n*P*mu*nf  # kN 抗滑
G=(m_total+m_ice)*9.81/1000
Fv=G; Fh=F
# 抗滑安全系数（竖向+水平合力）
Fres=math.hypot(Fv,Fh)
# 抗倾覆：力矩由螺栓群承担，螺栓间距 0.16 m
Mtot=M+G*0.35
Ftens=Mtot/0.16/2
res["clamp"]={"bolts":"4×M16-8.8","P_kN":P,"mu":mu,"slip_cap_kN":round(Fslip,1),"demand_kN":round(Fres,3),
 "SF_slip":round(Fslip/Fres,1),"M_overturn_kNm":round(Mtot,3),"bolt_tension_add_kN":round(Ftens,2),"SF_bolt_tension":round(P/ max(Ftens,1e-6),1)}
# 电气安全距离（DL/T 409-2023 表1 线路工作与带电体最小安全距离，交流）
sd={"110kV":1.5,"220kV":3.0,"330kV":4.0,"500kV":5.0,"750kV":8.0,"1000kV":9.5}
env=1.2  # 装置最大外包半径+安装人员活动裕量
res["safety_distance_m"]=sd
res["placement_rule"]={"device_envelope_m":env,"rule":"装置任一点至带电体距离 ≥ D_safe+0.5 m风偏裕量；500kV 需 ≥5.5 m，仅布于塔身下段主材(呼高以下)及地线支架"}
res["select"]={"a_m":a,"plate":"5052-H32 铝板 4 mm，平面度≤1 mm(≤λ/16@X)","dihedral_err":"≤0.2°"}
json.dump(res,open(os.path.join(os.path.dirname(__file__),"..","校核计算.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(json.dumps(res,ensure_ascii=False,indent=1))
