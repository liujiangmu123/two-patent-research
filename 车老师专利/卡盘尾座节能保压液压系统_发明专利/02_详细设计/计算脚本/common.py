# -*- coding: utf-8 -*-
"""公共工具：读取设计基准参数、写 JSON。单位：mm、MPa(=N/mm2)、N、mm3、s。"""
import json, math, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE_JSON = os.path.join(ROOT, "00_设计基准", "设计基准参数.json")
OUT = os.path.join(ROOT, "02_详细设计", "数据")
os.makedirs(OUT, exist_ok=True)

with open(BASE_JSON, encoding="utf-8") as f:
    B = json.load(f)

P_ATM = 0.101325  # MPa，绝对压力换算


def area(d):
    return math.pi * d * d / 4.0


def r(x, n=4):
    if isinstance(x, float):
        return float(f"{x:.{n}g}") if abs(x) >= 1e-12 else 0.0
    if isinstance(x, dict):
        return {k: r(v, n) for k, v in x.items()}
    if isinstance(x, list):
        return [r(v, n) for v in x]
    return x


def dump(name, data, script):
    data = {"_来源脚本": "02_详细设计/计算脚本/" + script,
            "_基准文件": "00_设计基准/设计基准参数.json 版本 " + B.get("版本", ""),
            "_生成时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            **r(data)}
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("写入", p)
    return data


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)


# ---------- 常用基准量 ----------
oil = B["油液"]; tail = B["尾座液压缸26"]; chuck = B["卡盘液压缸12"]
beta_lock = oil["有效体积模量_锁闭腔_MPa"]; beta_hose = oil["有效体积模量_含软管_MPa"]
alpha_oil = oil["体膨胀系数_1_K"]; rho = oil["密度_kg_m3"]
A1 = area(tail["缸径"]); A2 = A1 - area(tail["杆径"]); Ar = area(tail["杆径"])
S_tail = tail["行程"]; x_rated = tail["顶紧位置_伸出量_额定"]
Vd_block = B["锁闭容积"]["阀块直装缸体_每腔死容积"] * 1000.0  # mm3
Vd_hose = B["锁闭容积"]["常规软管连接_每腔附加容积"] * 1000.0
km_rated = B["尾座机械刚度"]["k_m_N_um"] * 1000.0  # N/mm
F0 = B["尾座推力"]["F0_额定"]; p_pre = B["预压"]["有杆腔预压压力_p_pre"]
Ac1 = area(chuck["缸径"]); Ac2 = Ac1 - area(chuck["杆径"])
pump = B["动力源"]; acc = B["蓄能器8"]


def chamber_volumes(x, vdead=Vd_block):
    """x：活塞伸出量 mm。返回无杆腔、有杆腔油液容积 mm3。"""
    return A1 * x + vdead, A2 * (S_tail - x) + vdead


def stiffness(x=x_rated, beta=beta_lock, km=km_rated, vdead=Vd_block, mode="dual"):
    """返回 (k1, k2, K) N/mm。mode: single 单腔锁闭（有杆腔通油箱）/ dual 双腔预压锁闭。"""
    V1, V2 = chamber_volumes(x, vdead)
    k1 = beta * A1 ** 2 / V1
    k2 = beta * A2 ** 2 / V2 if mode == "dual" else 0.0
    ko = k1 + k2
    return k1, k2, ko * km / (ko + km)


def p1_set(F, pp=p_pre):
    return (F + pp * A2) / A1
