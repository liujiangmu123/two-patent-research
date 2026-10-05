# -*- coding: utf-8 -*-
"""V11 发明专利申请文件一致性校验（读取 申请文件/_expanded.json 与文本源）。

用法：python check_patent_v11.py
检查：附图标记与名称一致、66 个标记全部在具体实施方式出现、各图均被引用且图中标记均有文字说明、
权利要求编号/引用/引用基础/句号、摘要字数、禁用词、段号连续、算例数值复算、权利要求数值在说明书中有支持。
"""
import json
import math
import os
import re
import sys

import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="06_申请文件")
ap.add_argument("--text", default="patent_text.js")
ap.add_argument("--desc", default="patent_desc.js")
ap.add_argument("--allow-todo", action="store_true", help="草稿阶段允许 TODO 残留（只记为提示）")
args = ap.parse_args()
OUT = os.path.join(PKG, args.out)
EXP = json.load(open(os.path.join(OUT, "_expanded.json"), encoding="utf-8"))
SRC = "".join(ln for f in (args.text, args.desc)
              for ln in open(os.path.join(HERE, f), encoding="utf-8") if not ln.lstrip().startswith("//"))
NFIG = len(EXP["fig_labels"])
BASE = json.load(open(os.path.join(PKG, "00_设计基准", "设计基准参数.json"), encoding="utf-8"))
USED = EXP["used_labels"]
NAME_ALL = EXP["names"]
NAME = {k: NAME_ALL[k] for k in USED}
problems, notes = [], []


def bad(msg):
    problems.append(msg)


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
        continue
    if not ab[:m.start()].endswith(NAME[k]):
        bad(f"摘要中标记 {k} 前的名称不是“{NAME[k]}”")
    if k not in fig_ab:
        bad(f"摘要中标记 {k} 未出现在摘要附图（图1）中")
if EXP["title"].replace("一种", "") not in ab:
    bad("摘要未包含发明名称")

# ------------------------------------------------------------------ 2 禁用词
alltext = ab + "".join(c["text"] for c in EXP["claims"]) + "".join(d["text"] for d in EXP["description"])
todos = sorted(set(re.findall(r"TODO\([^)]*\)", alltext)))
if todos:
    (notes.append if args.allow_todo else bad)(f"TODO 残留 {len(todos)} 处：{todos}")
for w in ("实用新型", "如权利要求", "XXX", "{", "}", "**", "最佳", "绝对", "零泄漏"):
    if w in alltext:
        bad(f"出现禁用词或未展开记号：{w}")

# ------------------------------------------------------------------ 3 权利要求
claims = EXP["claims"]
deps = {}
for i, c in enumerate(claims, 1):
    t = c["text"]
    if c["no"] != i or not t.startswith(f"{i}. "):
        bad(f"权利要求编号不连续：{c['no']}")
    if not t.endswith("。") or t.count("。") != 1:
        bad(f"权利要求 {i} 应以且仅以一个句号结束（句号数 {t.count('。')}）")
    refs = [int(x) for x in re.findall(r"权利要求(\d+)", t)]
    refs += [int(x) for x in re.findall(r"权利要求\d+或(\d+)", t)]
    for a_, b_ in re.findall(r"权利要求(\d+)至(\d+)", t):
        refs += list(range(int(a_), int(b_) + 1))
    for r in refs:
        if r >= i:
            bad(f"权利要求 {i} 引用了在后的权利要求 {r}")
    deps[i] = sorted(set(refs))
    body = t[len(f"{i}. "):]
    if not refs and not body.startswith("一种"):
        bad(f"独立权利要求 {i} 应以“一种”开头")
    if refs and "其特征在于" not in t and not body.startswith("一种"):
        bad(f"从属权利要求 {i} 缺少“其特征在于”")
    for m in re.finditer(r"（(\d+)）", t):
        k = m.group(1)
        if k not in NAME:
            bad(f"权利要求 {i} 中标记 {k} 不在附图中")
        elif not t[:m.start()].endswith(NAME[k]):
            bad(f"权利要求 {i} 中标记 {k} 前的名称不是“{NAME[k]}”")


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
        if pre.endswith("所述"):
            if k not in have:
                bad(f"权利要求 {i}：“所述{NAME[k]}（{k}）”缺少引用基础")
        have.add(k)
    intro[i] = have
notes.append("权利要求引用关系：" + "；".join(f"{i}←{deps[i]}" for i in deps if deps[i]))
indep = [i for i in deps if not deps[i] or claims[i - 1]["text"][len(f'{i}. '):].startswith("一种")]
for i in indep:      # 引用式独立权利要求的引用基础取被引用的权利要求
    pass
notes.append(f"独立权利要求：{indep}")
# 专利法实施细则第25条：多项从属权利要求只能以择一方式引用，且不得作为另一项多项从属权利要求的基础
multi = [i for i in deps if len(deps[i]) > 1]
for i in multi:
    if "或" not in claims[i - 1]["text"].split("所述")[0] and "任一项" not in claims[i - 1]["text"]:
        bad(f"多项从属权利要求 {i} 未以择一方式引用")
    for r in deps[i]:
        if r in multi:
            bad(f"多项从属权利要求 {i} 以多项从属权利要求 {r} 为基础")
notes.append(f"多项从属权利要求：{multi}（均未以另一项多项从属权利要求为基础）" if multi else "")

# ------------------------------------------------------------------ 4 说明书结构与段号
desc = EXP["description"]
heads = [d["text"] for d in desc if d["type"] == "h"]
if heads != ["技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式"]:
    bad(f"说明书部分标题顺序不对：{heads}")
nos = [int(d["no"][1:-1]) for d in desc if d.get("no")]
if nos != list(range(1, len(nos) + 1)):
    bad("段号不连续")
notes.append(f"说明书段落 {len(nos)} 段")
part = lambda p: " ".join(d["text"] for d in desc if d.get("part") == p and d["type"] != "labels")
impl, content, figdesc = part("具体实施方式"), part("发明内容"), part("附图说明")
background = part("背景技术") + part("技术领域")

# 背景技术不得出现附图标记
for k in USED:
    if re.search(re.escape(NAME[k]) + k + r"(?!\d)", background):
        bad(f"背景技术中出现附图标记 {k}")

# 66 个标记均在具体实施方式中以“名称+标记”出现
missing = [k for k in USED if not re.search(re.escape(NAME[k]) + k + r"(?!\d)", impl)]
if missing:
    bad(f"具体实施方式未出现的附图标记：{missing}")
notes.append(f"附图标记 {len(USED)} 个，具体实施方式全部出现" if not missing else "")

# 文本源中不得手写“名称+数字”（必须用记号）
for k in USED:
    for m in re.finditer(re.escape(NAME[k]) + r"[（(]?\d+", SRC):
        if SRC[m.start() - 1:m.start()] in ("'", '"') or SRC[m.end():m.end() + 1] in ("'", '"'):
            continue                      # 仿真结果 JSON 的键名（如 '导向测杆38'），不是正文
        bad(f"文本源中手写了附图标记：{SRC[m.start():m.end() + 4]}")

# 附图标记说明段与标记表一致
lab = " ".join(d["text"] for d in desc if d["type"] == "labels")
for k in USED:
    if f"{k}、{NAME[k]}" not in lab:
        bad(f"附图标记说明缺少 {k}、{NAME[k]}")

# ------------------------------------------------------------------ 5 附图引用
for n in range(1, NFIG + 1):
    if not re.search(rf"图{n}为", figdesc):
        bad(f"附图说明缺少图{n}")
    if not re.search(rf"图(?:\d+至)?{n}(?!\d)|图{n}(?!\d)", impl) and not re.search(rf"图\d+至图{n}(?!\d)", impl):
        # 允许“图1至图3”“图7至图9”形式覆盖
        covered = any(int(a) <= n <= int(b) for a, b in re.findall(r"图(\d+)至图(\d+)", impl))
        if not covered:
            bad(f"具体实施方式未引用图{n}")
    for k in EXP["fig_labels"][str(n)]:
        if not re.search(re.escape(NAME[k]) + k + r"(?!\d)", impl):
            bad(f"图{n} 中标记 {k} 未在具体实施方式中说明")

# ------------------------------------------------------------------ 6 权利要求的支持
for i, c in enumerate(claims, 1):
    for k in c["nums"]:
        if k in NAME and NAME[k] not in content:
            bad(f"权利要求 {i} 的特征“{NAME[k]}”未在发明内容中出现")
    for v in re.findall(r"\d+(?:\.\d+)?\s?m(?![a-zA-Z])", c["text"]):
        if v not in content:
            bad(f"权利要求 {i} 的数值“{v}”未在发明内容中出现")
for key in ("推力带", "二次侧溢流", "预压", "尾座轴向刚度"):
    if key not in impl:
        bad(f"具体实施方式未说明“{key}”")
for eqn in ("（1）", "（2）", "（4）", "（5）"):
    if f"式{eqn}" not in impl:
        bad(f"具体实施方式未引用式{eqn}")
for k in ("表1", "表2"):
    if not any(d["type"] == "table" and d["text"].startswith(k) for d in desc):
        bad(f"缺少{k}")
    if not re.search(k + r"(?!\d)", impl.replace(" ", "")):
        bad(f"正文未引用{k}")
for k in ("文献1", "文献2", "文献3", "文献4"):
    if k not in background:
        bad(f"背景技术缺少{k}")
for i in indep:
    t = claims[i - 1]["text"]
    for need in (("座阀",) if i == 1 else ()):
        if need not in t:
            bad(f"独立权利要求 {i} 缺少“{need}”")

# ------------------------------------------------------------------ 7 算例独立复算（Python 按设计基准参数重新计算，与说明书比对）
TC = BASE["尾座液压缸26"]
D_, d_, S_ = TC["缸径"], TC["杆径"], TC["行程"]
A1 = math.pi / 4 * D_ ** 2
A2 = math.pi / 4 * (D_ ** 2 - d_ ** 2)
oil = BASE["油液"]
km = BASE["尾座机械刚度"]["k_m_N_um"]
F0 = BASE["尾座推力"]["F0_额定"]
pp = BASE["预压"]["有杆腔预压压力_p_pre"]
full = " ".join(d["text"] for d in desc)


def lock(x, hose=False):
    Vd = (BASE["锁闭容积"]["阀块直装缸体_每腔死容积"] + (BASE["锁闭容积"]["常规软管连接_每腔附加容积"] if hose else 0)) * 1000
    b = oil["有效体积模量_含软管_MPa"] if hose else oil["有效体积模量_锁闭腔_MPa"]
    V1, V2 = A1 * x + Vd, A2 * (S_ - x) + Vd
    k1, k2 = b * A1 ** 2 / V1 / 1000, b * A2 ** 2 / V2 / 1000
    return dict(V1=V1 / 1000, V2=V2 / 1000, k1=k1, k2=k2, Ks=k1 * km / (k1 + km), Kd=(k1 + k2) * km / (k1 + k2 + km),
                Ts=b * oil["体膨胀系数_1_K"] * A1 * km / (k1 + km), Td=b * oil["体膨胀系数_1_K"] * (A1 - A2) * km / (k1 + k2 + km))


tab1 = next((d["text"] for d in desc if d["type"] == "table" and d["text"].startswith("表1")), "")
cnt = 0
for x, hose in ((20, False), (70, False), (130, False), (70, True)):
    r = lock(x, hose)
    for key, dg in (("V1", 1), ("V2", 1), ("k1", 1), ("k2", 1), ("Ks", 1), ("Kd", 1), ("Ts", 0), ("Td", 0)):
        v = f"{r[key]:.{dg}f}"
        cnt += 1
        if v not in tab1:
            bad(f"表1 复算值 x={x}{'（软管）' if hose else ''} {key}={v} 未在表中找到")
L = lock(70)
p1 = (F0 + pp * A2) / A1
want = {"A1": f"{A1:.1f}", "A2": f"{A2:.1f}", "p1set": f"{p1:.3f}",
        "p1set(2000)": f"{(2000 + pp * A2) / A1:.3f}", "p1set(12000)": f"{(12000 + pp * A2) / A1:.3f}",
        "单腔刚度": f"{L['Ks']:.1f}", "双腔刚度": f"{L['Kd']:.1f}", "单腔漂移": f"{L['Ts']:.0f}", "双腔漂移": f"{L['Td']:.0f}"}
band = 0.05 * F0
rate = BASE["油温扰动"]["锁闭腔油温漂移速率_K_min"]
want["越带时间(双腔,快)"] = f"{band / L['Td'] / rate[1]:.1f}"
want["越带时间(单腔,快)"] = f"{band / L['Ts'] / rate[1]:.1f}"
WP = BASE["工件热伸长"]["典型工件"][0]
want["热伸长推力(单腔)"] = f"{L['Ks'] * WP['伸长_um']:.0f}"
want["热伸长推力(双腔)"] = f"{L['Kd'] * WP['伸长_um']:.0f}"
want["ΔL 算例"] = f"{(band - round(L['Td'] * 0.1, 1)) / round(L['Kd'], 1):.2f}"
kmin = min(lock(x)["Kd"] for x in range(20, 131))
want["双腔刚度全行程下限"] = f"{math.floor(kmin * 10) / 10:.1f}"
for k, v in want.items():
    cnt += 1
    if v not in full:
        bad(f"算例复算 {k}={v} 未在说明书中找到")
# 与设计基准“额定工况推导值”核对
DV = BASE["额定工况推导值"]
for k, v in (("K_单腔锁闭_串联_N_um", L["Ks"]), ("K_双腔预压锁闭_串联_N_um", L["Kd"]),
             ("油温热漂移推力_单腔锁闭_N_K", L["Ts"]), ("油温热漂移推力_双腔锁闭_N_K", L["Td"])):
    if abs(DV[k] - v) > 0.06 * max(1, abs(v)) / 1 and abs(DV[k] - round(v, 1)) > 0.5:
        bad(f"复算值 {k}={v:.1f} 与设计基准 {DV[k]} 不一致")
notes.append(f"算例复算 {cnt} 项（A1={A1:.1f} mm2，A2={A2:.1f} mm2，p1set={p1:.3f} MPa，K 单/双={L['Ks']:.1f}/{L['Kd']:.1f} N/um，漂移 单/双={L['Ts']:.0f}/{L['Td']:.0f} N/K）")

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
