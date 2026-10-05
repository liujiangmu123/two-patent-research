# -*- coding: utf-8 -*-
"""按顺序复算全部计算脚本，并核对与设计基准参数.json 推导值的一致性。"""
import runpy, os, json
from common import B, load, dump
H = os.path.dirname(os.path.abspath(__file__))
for s in ["c01_缸与压力校核.py", "c02_刚度与热漂移.py", "c03_蓄能器与能耗.py", "c04_动作供油与控制参数.py", "c05_BOM与预算.py"]:
    runpy.run_path(os.path.join(H, s), run_name="__main__")
c2 = load("c02_刚度与热漂移.json"); c3 = load("c03_蓄能器与能耗.json"); ref = B["额定工况推导值"]
chk = []
def cmp(name, a, b, tol=0.01):
    chk.append({"项": name, "本计算": a, "基准": b, "相对差": abs(a - b) / abs(b), "通过": abs(a - b) / abs(b) <= tol})
s, d = c2["单腔锁闭_阀块直装"], c2["双腔预压锁闭_阀块直装"]
cmp("V1_cm3", s["V1_cm3"], ref["x=70mm时V1_cm3"]); cmp("V2_cm3", s["V2_cm3"], ref["V2_cm3"])
cmp("k1", s["k1_N_um"], ref["k1_油柱_N_um"]); cmp("k2", d["k2_N_um"], ref["k2_油柱_N_um"])
cmp("K单", s["K_N_um"], ref["K_单腔锁闭_串联_N_um"]); cmp("K双", d["K_N_um"], ref["K_双腔预压锁闭_串联_N_um"])
cmp("漂移单", s["油温漂移_N_K"], ref["油温热漂移推力_单腔锁闭_N_K"]); cmp("漂移双", d["油温漂移_N_K"], ref["油温热漂移推力_双腔锁闭_N_K"])
cmp("蓄能器等温可用", c3["蓄能器"]["可用容积_等温_cm3"], B["蓄能器8"]["可用容积_等温_cm3"], 0.03)
cmp("蓄能器绝热可用", c3["蓄能器"]["可用容积_绝热n1.4_cm3"], B["蓄能器8"]["可用容积_绝热_cm3"], 0.03)
dump("c00_基准一致性校核.json", {"校核": chk, "全部通过": all(c["通过"] for c in chk)}, "run_all.py")
