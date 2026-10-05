# -*- coding: utf-8 -*-
"""V1-11 主仿真（03_仿真验证/数据/*.json，v1.1）与独立复核（独立复核/数据/v1_*.json）逐项比对。
输出：独立复核/数据/v1_compare.json 与 v1_compare_table.md（独立复核报告第 1 节的表格）。
判定：|偏差| ≤2% 一致；2%~5% 基本一致；>5% 须在报告第 3 节说明原因（注“见 3.n”）。"""
import json, os
from v1_common import SIM, DATA, params, stiffness, dump, um

MAIN = os.path.join(SIM, "数据")


def J(d, n):
    t = open(os.path.join(d, n + ".json"), encoding="utf-8").read()
    return json.loads(t.replace("-Infinity", "null").replace("Infinity", "null").replace("NaN", "null"))


sc, st, en, ch, va, se, mc = (J(MAIN, n) for n in ("scen", "stiff", "energy", "chuck", "validate", "sens", "mc"))
vs, vq, vd, ve, ve0, vf, vc, vp, vl, vb, vm = (J(DATA, n) for n in (
    "v1_static", "v1_qs", "v1_dyn", "v1_energy", "v1_energy_v10", "v1_figcheck", "v1_chuck", "v1_ppre", "v1_dL", "v1_db", "v1_mc"))
W = sc["工况"]
C = {k.split()[0]: v for k, v in W.items()}
Q = {k.split()[0]: v for k, v in vq.items() if k[:2] in ("C1", "C2", "C3", "C4", "C5", "C6", "C7")}
DL = {k.split()[0]: v for k, v in sc["ΔL估算"].items() if "×0.1" not in k}
VDL = {k.split()[0]: v for k, v in vl.items() if k.startswith("C") and "×0.1" not in k}
rows = []


def add(cat, item, a, b, note="", unit="", dg=1, abs_tol=None):
    """a 主仿真值，b 复核值。abs_tol：数值很小时按绝对差判定（单位同 unit）。"""
    if a is None or b is None:
        dev, s = None, "—"
    else:
        dev = (b - a) / abs(a) * 100 if abs(a) > 1e-12 else 0.0
        s = f"{dev:+.1f}%"
    if dev is None:
        con = "—"
    elif abs_tol is not None and abs(b - a) <= abs_tol:
        con = "一致"
    elif abs(dev) <= 2:
        con = "一致"
    elif abs(dev) <= 5:
        con = "基本一致"
    else:
        con = "偏差>5%"
    if note:
        con += f"（{note}）"
    f = lambda v: "—" if v is None else (f"{v:.{dg}f}" if isinstance(v, float) else str(v))
    rows.append({"类别": cat, "项": item + (f" {unit}" if unit else ""), "主仿真值": f(a), "复核值": f(b), "偏差": s, "结论": con,
                 "dev": dev})


# ---------------- 静态
v = va["准静态模型_对解析式"]
add("静态", "单腔锁闭刚度（理想 β=1200）", v[1]["刚度数值N_um"], vs["有限差分核对"]["单腔"]["K_N_um"], unit="N/µm", dg=2)
add("静态", "双腔预压刚度（理想）", v[0]["刚度数值N_um"], vs["有限差分核对"]["双腔"]["K_N_um"], unit="N/µm", dg=2)
add("静态", "单腔热漂移系数（理想）", v[1]["热漂移数值N_K"], vs["有限差分核对"]["单腔"]["热漂移_N_K"], unit="N/K")
add("静态", "双腔热漂移系数（理想）", v[0]["热漂移数值N_K"], vs["有限差分核对"]["双腔"]["热漂移_N_K"], unit="N/K")
K = st["额定静刚度N_um"]
add("静态", "双腔刚度（空气 0.5%，额定 70 mm）", K["M2"], vs["空气0.5%"]["双腔"]["K_N_um"], unit="N/µm", dg=2)
add("静态", "单腔阀块直装刚度（空气 0.5%）", K["M2S"], vs["空气0.5%"]["单腔"]["K_N_um"], unit="N/µm", dg=2)
Ph = params(air=0.005, beta0=800e6)
add("静态", "单腔含软管刚度 M1s（β=800、+60 cm³、空气 0.5%）", K["M1s"],
    stiffness(Ph, Ph["F0"] / Ph["A1"], 0.0, dual=False, hose=True) * um, unit="N/µm", dg=2, note="复核按主仿真口径（整腔 β=800）另算")
add("静态", "单腔含软管刚度（复核原口径：仅软管段 β=800）", K["M1s"], vs["含软管(β_hose=800,每腔+60cm3)"]["单腔"]["K_N_um"],
    unit="N/µm", dg=2, note="见 3.6，口径不同")
add("静态", "双腔热漂移系数（空气 0.5%）", st["热漂移_含空气数值N_K"]["M2"], vs["空气0.5%"]["双腔"]["热漂移_N_K"], unit="N/K")
add("静态", "单腔热漂移系数（空气 0.5%）", st["热漂移_含空气数值N_K"]["M2S"], vs["空气0.5%"]["单腔"]["热漂移_N_K"], unit="N/K")
xs = st["伸出量mm"]
for x in (20, 130):
    i = min(range(len(xs)), key=lambda j: abs(xs[j] - x))
    r = next(rr for rr in vs["随伸出量"] if rr["x_mm"] == x)
    add("静态", f"双腔刚度 x={x} mm（空气 0.5%）", st["静刚度N_um"]["M2"][i], r["空气0.5%_K双"], unit="N/µm", dg=2)
for r in vp["p_pre扫描"]:
    m = next(rr for rr in st["p_pre扫描"] if abs(rr["p_pre"] - r["p_pre_MPa"]) < 1e-9)
    add("静态", f"p_pre={r['p_pre_MPa']:g} MPa 静刚度", m["K_N_um"], r["K_N_um"], unit="N/µm", dg=2,
        note="主仿真 v1.1 已修正 p1set 未随 p_pre 更新，见 3.2" if r["p_pre_MPa"] in (0.0, 3.0) else "")

# ---------------- 准静态保压
for c, nm in (("C1", "工件伸长 57.5 µm"), ("C2", "伸长 138 µm"), ("C3", "油温 +0.2 K/min"), ("C6", "综合")):
    a = DL[c]["M2_无测量误差"]["最大正偏差"]
    add("准静态", f"{c} {nm}，本发明 M2 最大正偏差（无测量误差）", a, Q[c]["M2"]["max_pos%"], unit="%", dg=2,
        note=("见 3.3；" if abs(Q[c]["M2"]["max_pos%"] / a - 1) > 0.05 else "") + f"主仿真计测量误差时 {C[c]['M2']['最大正偏差%']:.2f}")
for c in ("C1", "C2", "C3", "C6"):
    add("准静态", f"{c} 方案2 M1s（含软管）最大正偏差", C[c]["M1s"]["最大正偏差%"], Q[c]["M1s"]["max_pos%"], unit="%", dg=2,
        note="主仿真 v1.1 已改为含软管，见 3.1")
for c in ("C4", "C5", "C7"):
    a = DL[c]["M2_无测量误差"]["最大负偏差"]
    add("准静态", f"{c} 本发明最大负偏差（无测量误差）", a, Q[c]["M2"]["max_neg%"], unit="%", dg=2,
        note=("见 3.3；" if abs(Q[c]["M2"]["max_neg%"] / a - 1) > 0.05 else "") + f"主仿真计测量误差时 {C[c]['M2']['最大负偏差%']:.2f}")
for c in ("C1", "C5", "C7"):
    # 复核模型不计测量误差，故与主仿真“无测量误差”运行的回复次数比较（主仿真计入测量误差时见报告 3.3）
    a = DL[c]["M2_无测量误差"]["动作次数"]
    add("准静态", f"{c} 本发明回复次数（无测量误差）", a, Q[c]["M2"]["n_act"], unit="次", dg=0,
        note="见 3.3" if abs(Q[c]["M2"]["n_act"] / a - 1) > 0.05 else "")
sf = {(r["参数"], r["值"]): r for r in se["单因素"]}
add("准静态", "C6 静摩擦 300 N，本发明偏差", sf[("静摩擦N", 300.0)]["M2"]["最大偏差%"], vq["敏感性"]["Fs=300"]["C6 综合"]["M2_max_pos%"], unit="%", dg=2)
dbv = next(r for r in vb["扫描"] if r["F0_N"] == 2000 and r["δ"] == 0.05 and r["db_MPa"] == 0.05 and not r["设定下移db/2"])
add("准静态", "C6 F0=2000 N（回差 0.05 MPa），本发明偏差", sf[("目标推力N", 2000.0)]["M2"]["最大偏差%"], dbv["C6_max_pos%"], unit="%", dg=2,
    note="见 3.4")
for r in se["减压阀回差"]:
    if r["推力带δ"] != 0.05:
        continue
    vv = next(x for x in vb["扫描"] if x["F0_N"] == 6000 and x["δ"] == 0.05 and abs(x["db_MPa"] - r["回差MPa"]) < 1e-9
              and x["设定下移db/2"] == r["设定下移半个回差"])
    lab = f"回差 {r['回差MPa']:g} MPa{'、设定下移半个回差' if r['设定下移半个回差'] else ''}"
    add("准静态", f"C6 {lab}，回复次数", r["动作次数"], vv["C6_n"], unit="次", dg=0, note="见 3.4")

# ---------------- ΔL 估算（推力油温法，无测量误差）
for c in ("C1", "C2", "C3", "C4", "C5", "C6", "C7"):
    a = DL[c]["M2_无测量误差"]["推力油温法"]["最大绝对误差um"]
    b = VDL[c]["名义参数"]["最大绝对误差um"]
    add("ΔL 估算", f"{c} ΔL 最大绝对误差（式（4），无测量误差）", a, b, unit="µm", dg=1,
        note="见 3.5" if abs(b / a - 1) > 0.05 else "")

# ---------------- 动态
S = sc["切削力阶跃"]
for s, nm in (("M2", "本发明"), ("M2S", "单腔阀块直装"), ("M1s", "方案2")):
    add("动态", f"1 kN 阶跃，{nm}顶尖位移终值", abs(S[s]["1000"]["终值um"]), vd[s]["1000"]["终值um"], unit="µm", dg=1,
        note="见 3.7" if s == "M1s" else "")
add("动态", "1 kN 阶跃，本发明峰值", abs(S["M2"]["1000"]["峰值um"]), vd["M2"]["1000"]["峰值um"], unit="µm")
for F in ("500", "2000"):
    add("动态", f"{F} N 阶跃，本发明终值", abs(S["M2"][F]["终值um"]), vd["M2"][F]["终值um"], unit="µm")
add("动态", "1 kN 阶跃，方案3 恒压让位（0.3 s）", abs(S["M1b"]["1000"]["终值um"]) / 1e3, vd["M1b"]["1000"]["终值um"] / 1e3, unit="mm",
    dg=2, note="见 3.7，只作定性")

# ---------------- 能耗
add("能耗", "原系统 M0 保压泵轴功率", en["保压630s"]["M0"]["平均轴功率W"], ve["M0"]["液压功率W"] / 0.97, unit="W")
add("能耗", "原系统 M0 单件电能", en["单件循环"]["M0"]["单件电能kWh"] * 1e3, ve["M0"]["按物理_液压功率/η_hm0.97/η_m_单件Wh"], unit="Wh")
add("能耗", "现有间歇保压（方案2/3）单件电能（复核 v1.0 口径）", en["单件循环"]["M1s"]["单件电能kWh"] * 1e3,
    ve0["现有间歇保压_c_red=1(C)"]["单件Wh"], unit="Wh", note="见 3.8")
add("能耗", "现有间歇保压（方案2/3）单件电能（复核 v1.1 口径）", en["单件循环"]["M1s"]["单件电能kWh"] * 1e3,
    ve["现有间歇保压_c_red=1(C)"]["单件Wh"], unit="Wh")
add("能耗", "本发明单件电能（复核 v1.0 口径）", en["单件循环"]["M2"]["单件电能kWh"] * 1e3, ve0["本发明_基准(60s,1s)"]["单件Wh"], unit="Wh",
    dg=2, note="见 3.8")
add("能耗", "本发明单件电能（复核 v1.1 口径）", en["单件循环"]["M2"]["单件电能kWh"] * 1e3, ve["本发明_基准(60s,1s)"]["单件Wh"], unit="Wh",
    dg=2, note="见 3.8")
add("能耗", "本发明相对原系统节电率", en["相对M0节能%"]["M2"], ve["本发明_基准(60s,1s)"]["相对M0节电%(口径A)"], unit="%", dg=1)

# ---------------- 卡盘
for k in ("油温降0.2K/min_复压30s", "油温降0.2K/min_复压60s", "油温降0.2K/min_复压120s", "油温降0.05K/min_复压60s"):
    add("卡盘", f"{k.replace('_', '，')} 最大夹紧力降", ch["工况"][k]["最大夹紧力降%"], vc["工况"][k]["最大夹紧力降%"], unit="%", dg=2)
add("卡盘", "复压 60 s，630 s 耗油", ch["工况"]["油温降0.2K/min_复压60s"]["耗油cm3"], vc["工况"]["油温降0.2K/min_复压60s"]["耗油cm3"], unit="cm³")
add("卡盘", "现有技术回转接头持续带压 630 s 耗油", ch["现有技术_回转接头持续带压"]["耗油cm3"], vc["现有技术_回转接头持续带压_630s耗油cm3"], unit="cm³")
add("卡盘", "允许降 5% 的最长复压间隔（−0.2 K/min）", ch["允许降5%时最长复压间隔s_0.2K/min"], vc["允许降5%时最长复压间隔s_0.2K/min"], unit="s")

# ---------------- 蒙特卡洛
mm = mc["汇总"]
add("蒙特卡洛", "本发明最大偏差 P95", mm["M2"]["P95%"], vm["汇总"]["M2"]["P95%"], unit="%", dg=2, note="见 3.9")
add("蒙特卡洛", "方案2（含软管）最大偏差 P95", mm["M1s"]["P95%"], vm["汇总"]["M1s"]["P95%"], unit="%", dg=2, note="见 3.9")
add("蒙特卡洛", "方案2 超安全上限 1.25F0 比例", 100 * mm["M1s"]["超安全上限25%比例"], 100 * vm["汇总"]["M1s"]["超安全上限25%比例"], unit="%",
    dg=1, note="见 3.9")
add("蒙特卡洛", "本发明超安全上限比例", 100 * mm["M2"]["超安全上限25%比例"], 100 * vm["汇总"]["M2"]["超安全上限25%比例"], unit="%", dg=1,
    abs_tol=0.1)

# ---------------- 附图
for fg, keys in (("图16", ("M1s", "M1b", "M2")), ("图17", ("M1s", "M2S", "M2"))):
    for k in keys:
        d = vf[fg][k]
        add("附图", f"{fg} {k} 曲线终值（SVG 反解 / JSON）", d["终值(JSON)"], d["曲线终值(图)"], dg=3, abs_tol=1e-3)
for k in ("M0", "M1s", "M2"):
    d = vf["图18"][k]
    add("附图", f"图18 {k} 终值（SVG / JSON）", d["单件电能(JSON)Wh"], d["终值(图)Wh"], unit="Wh", dg=2, abs_tol=0.01)

dump("v1_compare", {"表": rows})
hdr = "| 类别 | 项 | 主仿真值 | 复核值 | 偏差 | 结论 |\n| --- | --- | --- | --- | --- | --- |\n"
md = hdr + "".join(f"| {r['类别']} | {r['项']} | {r['主仿真值']} | {r['复核值']} | {r['偏差']} | {r['结论']} |\n" for r in rows)
open(os.path.join(DATA, "v1_compare_table.md"), "w", encoding="utf-8").write(md)
n5 = sum(1 for r in rows if r["dev"] is not None and abs(r["dev"]) > 5 and "一致" not in r["结论"][:2])
print(f"{len(rows)} 项，偏差>5% {n5} 项")
