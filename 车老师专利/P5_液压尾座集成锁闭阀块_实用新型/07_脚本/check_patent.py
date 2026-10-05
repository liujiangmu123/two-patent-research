# -*- coding: utf-8 -*-
r"""P5 实用新型申请文件一致性校验（读 06_申请文件/_expanded.json 与文本源）。复制自 P1 的 check_patent.py 后改写，P1 原文件未改动。

用法：.venv\Scripts\python.exe 07_脚本\check_patent.py
检查：
  1 摘要字数、摘要标记在摘要附图中、名称出现
  2 禁用词（本发明、发明内容、TODO 等）、全文须用“实用新型”
  3 权利要求编号/引用/择一引用/引用基础/句号；**权利要求中不得出现方法步骤或控制算法用语**（实用新型保护客体）
  4 说明书五部分标题（第三部分为“实用新型内容”）、段号连续、背景技术无标记
  5 全部标记在具体实施方式以“名称+标记”出现；附图说明与具体实施方式引用每幅图；图中标记均有文字说明；标记说明段齐全
  6 权利要求特征名称与数值在实用新型内容中有支持；表1、表2 存在并被引用；文献1~3 在背景技术中
  7 数值复核：按 04_模型/_check_report.json 的 CAD 容积与 P1 共用参数独立复算死容积与锁闭刚度，并与 03_校核计算/校核计算.json、说明书文字比对；
    权利要求 10、11、14 的数值界限与设计基准/校核结果相符
输出：06_申请文件/_校验报告.txt；有问题时退出码 1。
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
OUT = os.path.join(PKG, "06_申请文件")
EXP = json.load(open(os.path.join(OUT, "_expanded.json"), encoding="utf-8"))
SRC = "".join(ln for f in ("patent_text.js", "patent_desc.js")
              for ln in open(os.path.join(HERE, f), encoding="utf-8") if not ln.lstrip().startswith("//"))
B5 = json.load(open(os.path.join(PKG, "00_设计基准", "P5_设计基准.json"), encoding="utf-8"))
B1 = json.load(open(os.path.normpath(os.path.join(PKG, B5["P1基准"]["文件"])), encoding="utf-8"))
CJ = json.load(open(os.path.join(PKG, "03_校核计算", "校核计算.json"), encoding="utf-8"))
CAD = json.load(open(os.path.join(PKG, "04_模型", "_check_report.json"), encoding="utf-8"))
NFIG = len(EXP["fig_labels"])
USED = EXP["used_labels"]
NAME = {k: EXP["names"][k] for k in USED}
problems, notes = [], []
bad = problems.append

# ------------------------------------------------------------------ 1 摘要
ab = EXP["abstract"]
n_ab = len(re.sub(r"\s", "", ab))
notes.append(f"摘要字数 {n_ab}")
if n_ab > 300:
    bad(f"摘要超过 300 字：{n_ab}")
fig_ab = set(EXP["fig_labels"]["1"])
for m in re.finditer(r"（(\d+)）", ab):
    k = m.group(1)
    if k not in NAME:
        bad(f"摘要中标记 {k} 不在附图中")
    elif not ab[:m.start()].endswith(NAME[k]):
        bad(f"摘要中标记 {k} 前的名称不是“{NAME[k]}”")
    elif k not in fig_ab:
        bad(f"摘要中标记 {k} 未出现在摘要附图（图1）中")
if EXP["title"].replace("一种", "") not in ab:
    bad("摘要未包含实用新型名称")

# ------------------------------------------------------------------ 2 禁用词
claims_text = "".join(c["text"] for c in EXP["claims"])
desc_text = "".join(d["text"] for d in EXP["description"])
alltext = ab + claims_text + desc_text
todos = sorted(set(re.findall(r"TODO\([^)]*\)", alltext)))
notes.append(f"TODO 残留 {len(todos)} 处")
if todos:
    bad(f"TODO 残留：{todos}")
for w in ("本发明", "发明内容", "发明专利", "该发明", "如权利要求", "XXX", "{", "}", "**", "最佳", "绝对", "零泄漏", "undefined", "NaN"):
    if w in alltext:
        bad(f"出现禁用词或未展开记号：{w}")
if "本实用新型" not in ab + desc_text:
    bad("全文未使用“本实用新型”")

# ------------------------------------------------------------------ 3 权利要求
claims = EXP["claims"]
deps = {}
METHOD = ("步骤", "方法", "控制器", "控制", "算法", "计算", "配置为", "程序", "判断", "估算", "检测出", "钻入", "钻出", "加工", "焊接",
          "工艺", "时，使", "然后", "首先")
for i, c in enumerate(claims, 1):
    t = c["text"]
    if c["no"] != i or not t.startswith(f"{i}. "):
        bad(f"权利要求编号不连续：{c['no']}")
    if not t.endswith("。") or t.count("。") != 1:
        bad(f"权利要求 {i} 应以且仅以一个句号结束（句号数 {t.count('。')}）")
    for w in METHOD:
        if w in t:
            bad(f"权利要求 {i} 含方法或控制用语“{w}”（实用新型只保护结构）")
    refs = [int(x) for x in re.findall(r"权利要求(\d+)", t)]
    refs += [int(x) for x in re.findall(r"权利要求\d+或(\d+)", t)]
    for a_, b_ in re.findall(r"权利要求(\d+)至(\d+)", t):
        refs += list(range(int(a_), int(b_) + 1))
    for r in refs:
        if r >= i:
            bad(f"权利要求 {i} 引用了在后的权利要求 {r}")
    deps[i] = sorted(set(refs))
    body = t[len(f"{i}. "):]
    if not body.startswith("一种") and not body.startswith("根据权利要求"):
        bad(f"权利要求 {i} 开头不规范")
    if "其特征在于" not in t:
        bad(f"权利要求 {i} 缺少“其特征在于”")
    for m in re.finditer(r"（(\d+)）", t):
        k = m.group(1)
        if k not in NAME:
            bad(f"权利要求 {i} 中标记 {k} 不在附图中")
        elif not t[:m.start()].endswith(NAME[k]):
            bad(f"权利要求 {i} 中标记 {k} 前的名称不是“{NAME[k]}”")
indep = [i for i in deps if claims[i - 1]["text"][len(f'{i}. '):].startswith("一种")]
notes.append(f"独立权利要求：{indep}；权利要求共 {len(claims)} 项")


def ancestors(i, seen=None):
    seen = seen if seen is not None else set()
    for r in deps[i]:
        if r not in seen:
            seen.add(r)
            ancestors(r, seen)
    return seen


intro = {}
for i, c in enumerate(claims, 1):
    t = c["text"]
    have = set()
    for a in ancestors(i):
        have |= intro[a]
    for m in re.finditer(r"（(\d+)）", t):
        k = m.group(1)
        if k not in NAME:
            continue
        pre = t[:m.start() - len(NAME[k])]
        if pre.endswith("所述") and k not in have:
            bad(f"权利要求 {i}：“所述{NAME[k]}（{k}）”缺少引用基础")
        have.add(k)
    intro[i] = have
multi = [i for i in deps if len(deps[i]) > 1]
for i in multi:
    head = claims[i - 1]["text"].split("所述")[0]
    if "或" not in head and "任一项" not in head:
        bad(f"多项从属权利要求 {i} 未以择一方式引用")
notes.append(f"多项从属权利要求 {multi}（细则第25条：多项从属可作为另一项多项从属的基础时须核对，见下）")
for i in multi:
    for r in deps[i]:
        if r in multi:
            bad(f"多项从属权利要求 {i} 以多项从属权利要求 {r} 为基础")

# ------------------------------------------------------------------ 4 说明书结构
desc = EXP["description"]
heads = [d["text"] for d in desc if d["type"] == "h"]
if heads != ["技术领域", "背景技术", "实用新型内容", "附图说明", "具体实施方式"]:
    bad(f"说明书部分标题顺序不对：{heads}")
nos = [int(d["no"][1:-1]) for d in desc if d.get("no")]
if nos != list(range(1, len(nos) + 1)):
    bad("段号不连续")
notes.append(f"说明书段落 {len(nos)} 段")


def part(p):
    return " ".join(d["text"] for d in desc if d.get("part") == p and d["type"] != "labels")


impl, content, figdesc = part("具体实施方式"), part("实用新型内容"), part("附图说明")
background = part("背景技术") + part("技术领域")
for k in USED:
    if re.search(re.escape(NAME[k]) + k + r"(?!\d)", background):
        bad(f"背景技术中出现附图标记 {k}")

# ------------------------------------------------------------------ 5 标记与附图
missing = [k for k in USED if not re.search(re.escape(NAME[k]) + k + r"(?!\d)", impl)]
if missing:
    bad(f"具体实施方式未出现的附图标记：{missing}")
notes.append(f"附图标记 {len(USED)} 个" + ("，具体实施方式全部出现" if not missing else ""))
for k in USED:
    for m in re.finditer(re.escape(NAME[k]) + r"[（(]?\d+", SRC):
        bad(f"文本源中手写了附图标记：{SRC[m.start():m.end() + 4]}")
lab = " ".join(d["text"] for d in desc if d["type"] == "labels")
for k in USED:
    if f"{k}、{NAME[k]}" not in lab:
        bad(f"附图标记说明缺少 {k}、{NAME[k]}")
for n in range(1, NFIG + 1):
    if not re.search(rf"图{n}为", figdesc):
        bad(f"附图说明缺少图{n}")
    covered = re.search(rf"图{n}(?!\d)", impl) or any(int(a) <= n <= int(b) for a, b in re.findall(r"图(\d+)至图(\d+)", impl))
    if not covered:
        bad(f"具体实施方式未引用图{n}")
    for k in EXP["fig_labels"][str(n)]:
        if not re.search(re.escape(NAME[k]) + k + r"(?!\d)", impl):
            bad(f"图{n} 中标记 {k} 未在具体实施方式中说明")

# ------------------------------------------------------------------ 6 支持
for i, c in enumerate(claims, 1):
    for k in c["nums"]:
        if k in NAME and NAME[k] not in content:
            bad(f"权利要求 {i} 的特征“{NAME[k]}”未在实用新型内容中出现")
    for v in re.findall(r"\d+(?:\.\d+)?\s?(?:mm|cm3|cm\^\{3\}|cm³|MPa)", c["text"]):
        if v not in content:
            bad(f"权利要求 {i} 的数值“{v}”未在实用新型内容中出现")
    nums = re.findall(r"不大于 (\d+(?:\.\d+)?) ", c["text"])
    for v in nums:
        if v not in content:
            bad(f"权利要求 {i} 的数值界限 {v} 未在实用新型内容中出现")
for k in ("表1", "表2"):
    if not any(d["type"] == "table" and d["text"].startswith(k) for d in desc):
        bad(f"缺少{k}")
    if not re.search(k + r"(?!\d)", impl.replace(" ", "")):
        bad(f"正文未引用{k}")
for k in ("文献1", "文献2", "文献3"):
    if k not in background:
        bad(f"背景技术缺少{k}")
t1 = claims[0]["text"]
for need in ("同轴", "直的", "相交", "一端封闭", "锁闭座阀"):
    if need not in t1:
        bad(f"独立权利要求 1 缺少核心特征用语“{need}”")

# ------------------------------------------------------------------ 7 数值复核（独立复算）
full = " ".join(d["text"] for d in desc)
TC = B1["尾座液压缸26"]
A1 = math.pi / 4 * TC["缸径"] ** 2
A2 = math.pi / 4 * (TC["缸径"] ** 2 - TC["杆径"] ** 2)
beta, betaH = B1["油液"]["有效体积模量_锁闭腔_MPa"], B1["油液"]["有效体积模量_含软管_MPa"]
km = B1["尾座机械刚度"]["k_m_N_um"] * 1000
S_ = TC["行程"]
cv = CAD["锁闭容积_CAD"]
tb = B5["尾座油缸"]["活塞限位凸台"]
gapC = tb["无杆腔侧"]["h"] * (A1 - math.pi / 4 * tb["无杆腔侧"]["D"] ** 2)
gapR = tb["有杆腔侧"]["h"] * (A2 - math.pi / 4 * (tb["有杆腔侧"]["D_out"] ** 2 - tb["有杆腔侧"]["D_in"] ** 2))
est = (B5["测压与测温"]["压力传感器"]["膜片前腔容积_cm3"] + B5["测压与测温"]["测压排气接头"]["单向阀前腔容积_cm3"]) * 1000
bvR = cv["有杆腔"]["扣除插入元件后_cm3"] * 1000 + est
bvC = cv["无杆腔"]["扣除插入元件后_cm3"] * 1000 + est
dvR = bvR + cv["缸体油道_有杆腔_cm3"] * 1000 + gapR
dvC = bvC + cv["缸体油道_无杆腔_cm3"] * 1000 + gapC


def kd(x, v1, v2, b):
    k1, k2 = b * A1 ** 2 / (A1 * x + v1), b * A2 ** 2 / (A2 * (S_ - x) + v2)
    return (k1 + k2) * km / (k1 + k2 + km) / 1000


K5 = kd(70, dvC, dvR, beta)
VH = (B1["锁闭容积"]["阀块直装缸体_每腔死容积"] + B1["锁闭容积"]["常规软管连接_每腔附加容积"]) * 1000
KH = kd(70, VH, VH, betaH)
want = {"有杆腔死容积": f"{dvR / 1000:.2f}", "无杆腔死容积": f"{dvC / 1000:.2f}", "阀块侧有杆腔": f"{bvR / 1000:.2f}",
        "阀块侧无杆腔": f"{bvC / 1000:.2f}", "双腔刚度P5": f"{K5:.1f}", "双腔刚度软管": f"{KH:.1f}", "刚度提高%": f"{(K5 / KH - 1) * 100:.0f}",
        "A1": f"{A1:.1f}", "A2": f"{A2:.1f}"}
S = CJ["汇总"]
for k, v in want.items():
    if v not in full:
        bad(f"复算 {k}={v} 未在说明书中找到")
for k, (a, b_) in {"有杆腔死容积": (dvR / 1000, S["每腔死容积_有杆腔_cm3"]), "无杆腔死容积": (dvC / 1000, S["每腔死容积_无杆腔_cm3"]),
                   "双腔刚度P5": (K5, S["x70双腔刚度_P5_N_um"]), "双腔刚度软管": (KH, S["x70双腔刚度_软管_N_um"])}.items():
    if abs(a - b_) > 0.051:
        bad(f"复算 {k}={a:.3f} 与校核计算 JSON {b_} 不一致")
for key, dg in (("阀块孔道压降_25Lmin_40C_MPa", 3), ("缸体油道压降_25Lmin_40C_MPa", 3), ("最小壁厚_mm", 1), ("最小安全系数_设计压力", 1),
                ("螺栓预紧对分离力倍数", 1)):
    v = f"{S[key]:.{dg}f}"
    if v not in full:
        bad(f"校核结果 {key}={v} 未在说明书中找到")
# 权利要求数值界限的真实性
if not (dvR / 1000 <= 15 and dvC / 1000 <= 15):
    bad("权利要求 14：死容积超过 15 cm3")
if not (bvR / 1000 <= 10 and bvC / 1000 <= 10):
    bad("权利要求 11：阀块侧锁闭孔系容积超过 10 cm3")
tw = B5["测压与测温"]["油温传感器套管"]
if not (tw["外径"] <= 6 and tw["端部壁厚"] <= 1.0):
    bad("权利要求 10：套管尺寸与设计基准不符")
if S["最小安全系数_设计压力"] < B5["阀块本体"]["安全系数_要求"]:
    bad("最小壁厚安全系数低于要求")
notes.append(f"数值复核：死容积 {dvR / 1000:.2f}/{dvC / 1000:.2f} cm3，阀块侧 {bvR / 1000:.2f}/{bvC / 1000:.2f} cm3，"
             f"双腔刚度 {K5:.1f}（软管 {KH:.1f}）N/um，与校核计算 JSON 一致")

# ------------------------------------------------------------------ 结果
lines = [n for n in notes if n] + ["-" * 60]
if problems:
    lines.append(f"发现 {len(problems)} 个问题：")
    lines += ["  ✗ " + p for p in problems]
else:
    lines.append("全部检查通过 ✓")
report = "\n".join(lines)
with open(os.path.join(OUT, "_校验报告.txt"), "w", encoding="utf-8") as fh:
    fh.write(report + "\n")
print(report)
sys.exit(1 if problems else 0)
