# -*- coding: utf-8 -*-
"""C02 锁闭刚度、油温热漂移、工件热伸长、泄漏引起的推力变化 -> 数据/c02_刚度与热漂移.json

准静态线性模型（推导见说明书 4.2）：
  活塞向工件方向位移 du，机械链（尾座体+套筒+顶尖+工件）刚度 km，工件热伸长 dδ。
  dp1 = β/V1·(−q12 − A1·du + α·V1·dT)
  dp2 = β/V2·( q12 − q2t + A2·du + α·V2·dT)     （单腔锁闭时 p2≡0，k2=0）
  dF  = A1·dp1 − A2·dp2 = km·(du + dδ)
 => dF = km/(k_oil+km)·[ β·α·dT·(A1−A2) − β·q12·(A1/V1+A2/V2) + β·q2t·A2/V2 + k_oil·dδ ]
"""
from common import *


def response(mode="dual", x=x_rated, beta=beta_lock, km=km_rated, vdead=Vd_block):
    V1, V2 = chamber_volumes(x, vdead)
    k1, k2, K = stiffness(x, beta, km, vdead, mode)
    ko = k1 + k2
    g = km / (ko + km)
    if mode == "dual":
        Fsrc_T = beta * alpha_oil * (A1 - A2)
        Fsrc_q = beta * (A1 / V1 + A2 / V2)        # N per mm3 净转移 1→2
    else:
        Fsrc_T = beta * alpha_oil * A1
        Fsrc_q = beta * A1 / V1                     # N per mm3 从无杆腔漏出
    return {"V1_cm3": V1 / 1e3, "V2_cm3": V2 / 1e3, "k1_N_um": k1 / 1e3, "k2_N_um": k2 / 1e3,
            "K_N_um": K / 1e3, "油温漂移_N_K": g * Fsrc_T, "泄漏灵敏度_N_per_cm3": g * Fsrc_q * 1e3,
            "工件伸长灵敏度_N_um": K / 1e3}


res = {}
modes = {"单腔锁闭_阀块直装": ("single", Vd_block), "双腔预压锁闭_阀块直装": ("dual", Vd_block),
         "单腔锁闭_含软管": ("single", Vd_block + Vd_hose), "双腔预压锁闭_含软管": ("dual", Vd_block + Vd_hose)}
for k, (m, vd) in modes.items():
    beta = beta_lock if vd == Vd_block else beta_hose
    res[k] = response(m, beta=beta, vdead=vd)
res["_注"] = "含软管工况同时取 β=800 MPa（基准 '有效体积模量_含软管'）与每腔附加 60 cm3"

# 1 位置敏感性
res["随顶紧位置x"] = []
for x in [20, 40, 70, 100, 130]:
    s = response("single", x); d = response("dual", x)
    res["随顶紧位置x"].append({"x_mm": x, "K单_N_um": s["K_N_um"], "K双_N_um": d["K_N_um"],
                           "漂移单_N_K": s["油温漂移_N_K"], "漂移双_N_K": d["油温漂移_N_K"]})
# 2 β、km 敏感性
res["随beta"] = [{"beta": b, "K单": response("single", beta=b)["K_N_um"], "K双": response("dual", beta=b)["K_N_um"],
                 "漂移单": response("single", beta=b)["油温漂移_N_K"], "漂移双": response("dual", beta=b)["油温漂移_N_K"]}
                for b in [800, 1000, 1200, 1400, 1600]]
res["随km"] = [{"km_N_um": k, "K单": response("single", km=k * 1e3)["K_N_um"], "K双": response("dual", km=k * 1e3)["K_N_um"],
               "漂移单": response("single", km=k * 1e3)["油温漂移_N_K"], "漂移双": response("dual", km=k * 1e3)["油温漂移_N_K"]}
              for k in [50, 100, 200]]

# 3 预压的作用：p_pre 不改变线性刚度（β 视为常数），但保证 p2 不跌破气体析出压力
d = response("dual")
dF_band = 0.05 * F0
dT_trig_s = dF_band / response("single")["油温漂移_N_K"]
dT_trig_d = dF_band / d["油温漂移_N_K"]
res["推力带触发"] = {"带宽_N(±5%F0)": dF_band, "单腔触发油温变化_K": dT_trig_s, "双腔触发油温变化_K": dT_trig_d}
rows = []
for rate in B["油温扰动"]["锁闭腔油温漂移速率_K_min"] + [0.05, 0.1]:
    rows.append({"油温速率_K_min": rate, "单腔越带时间_min": dT_trig_s / rate, "双腔越带时间_min": dT_trig_d / rate})
res["油温漂移越带时间"] = sorted(rows, key=lambda r_: r_["油温速率_K_min"])
res["日变化5K推力变化_N"] = {"单腔": 5 * response("single")["油温漂移_N_K"], "双腔": 5 * d["油温漂移_N_K"]}

# 4 工件热伸长
alpha_s = B["工件热伸长"]["线膨胀系数_钢_1_K"]
wl = []
for w in B["工件热伸长"]["典型工件"]:
    dl = alpha_s * w["长度"] * w["平均温升_K"] * 1e3  # um
    Ec = 2.06e5; I = math.pi * w["直径"] ** 4 / 64
    Fcr = math.pi ** 2 * Ec * I / w["长度"] ** 2      # 两端铰支欧拉临界力（顶尖支承近似）
    for nm, m in [("单腔", "single"), ("双腔", "dual")]:
        K = response(m)["K_N_um"]
        dF = K * dl
        Fend = F0 + dF
        wl.append({"工件": f"Ø{w['直径']}×{w['长度']}", "ΔT_K": w["平均温升_K"], "伸长_um": dl, "方式": nm,
                   "推力增量_N": dF, "末推力_N": Fend, "欧拉临界力_N": Fcr,
                   "弯曲放大1/(1-F/Fcr)": (1 / (1 - Fend / Fcr)) if Fend < Fcr else None,
                   "额定F0放大": 1 / (1 - F0 / Fcr) if F0 < Fcr else None,
                   "越带所需伸长_um": dF_band / K})
res["工件热伸长"] = wl
res["工件热伸长_注"] = "Ø20×800 工件 Fcr≈25 kN，F0=6 kN 时弯曲放大 1.32，锁闭后热伸长使推力升至 10.6~12.3 kN、放大 1.74~1.97；双腔刚度更高，热伸长引起的推力增量更大，必须依靠越带回复（每伸长约 6.6 µm 回复一次）"

# 5 泄漏引起的推力变化率
c_in = tail["活塞内泄漏系数_cm3_min_MPa"] * 1e3 / 60.0  # mm3/s/MPa
c_seat = 1e-4 * 1e3 / 60.0
c_spool = B["阀"]["滑阀泄漏_每阀_cm3_min_MPa"] * 1e3 / 60.0
p1 = p1_set(F0)
leak = {}
# 双腔：活塞内泄 1->2；座阀 V1 反向压差 p1-? 座阀下游锁闭期间接 R1 出口 ≈ 其自身压力，取最坏全压差
for nm, mode, q12, q2t in [
    ("双腔预压锁闭_座阀", "dual", c_in * (p1 - p_pre), c_seat * p_pre),
    ("单腔锁闭_座阀", "single", c_in * p1 + c_seat * p1, 0.0),
    ("单腔锁闭_换向滑阀中位锁闭(对照)", "single", c_in * p1 + c_spool * p1, 0.0)]:
    rr = response(mode)
    if mode == "dual":
        V1, V2 = chamber_volumes(x_rated)
        g = km_rated / (rr["k1_N_um"] * 1e3 + rr["k2_N_um"] * 1e3 + km_rated)
        rate = g * beta_lock * (q12 * (A1 / V1 + A2 / V2) - q2t * A2 / V2) + g * beta_lock * c_seat * p1 * A1 / V1
    else:
        rate = rr["泄漏灵敏度_N_per_cm3"] / 1e3 * q12
    rate_min = rate * 60
    leak[nm] = {"推力下降速率_N_min": rate_min, "越下限时间_min": dF_band / rate_min,
                "越下限时间_h": dF_band / rate_min / 60}
res["泄漏推力衰减"] = leak
res["泄漏_注"] = "双腔：活塞内泄 1→2 同时降 p1、升 p2，两者都使推力下降；V1、V2 座阀泄漏按 1e-4 cm3/min/MPa、最坏全压差计"
res["内泄漏敏感性"] = [{"倍数": m, "双腔越下限_h": leak["双腔预压锁闭_座阀"]["越下限时间_h"] / m}
                    for m in tail["内泄漏敏感性倍数"] + [1]]

dump("c02_刚度与热漂移.json", res, "c02_刚度与热漂移.py")
