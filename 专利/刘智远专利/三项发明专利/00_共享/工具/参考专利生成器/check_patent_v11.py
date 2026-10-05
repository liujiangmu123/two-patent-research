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
ap = argparse.ArgumentParser()
ap.add_argument("--root", default="06_发明专利申请_V11")
ap.add_argument("--text", default="patent_v11_text.js")
ap.add_argument("--desc", default="patent_v11_desc.js")
args = ap.parse_args()
ROOT = os.path.join(os.path.dirname(HERE), args.root)
EXP = json.load(open(os.path.join(ROOT, "申请文件", "_expanded.json"), encoding="utf-8"))
NUM = json.load(open(os.path.join(HERE, "v11_patent_numerals.json"), encoding="utf-8"))
SRC = "".join(ln for f in (args.text, args.desc)
              for ln in open(os.path.join(HERE, f), encoding="utf-8") if not ln.lstrip().startswith("//"))
NFIG = len(EXP["fig_labels"])

USED = EXP["used_labels"]
NAME = {k: NUM[k]["name"] for k in USED}
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
for w in ("实用新型", "如权利要求", "TODO", "XXX", "{", "}", "**"):
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
    for r in refs:
        if r >= i:
            bad(f"权利要求 {i} 引用了在后的权利要求 {r}")
    deps[i] = sorted(set(refs))
    body = t[len(f"{i}. "):]
    if not refs and not body.startswith("一种"):
        bad(f"独立权利要求 {i} 应以“一种”开头")
    if refs and "其特征在于" not in t:
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
notes.append(f"独立权利要求：{indep}")
# 专利法实施细则第25条：多项从属权利要求只能以择一方式引用，且不得作为另一项多项从属权利要求的基础
multi = [i for i in deps if i not in indep and len(deps[i]) > 1]
for i in multi:
    if "或" not in claims[i - 1]["text"].split("所述")[0]:
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
        if SRC[m.end():m.end() + 1] in ("'", '"'):
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
        if NAME[k] not in content:
            bad(f"权利要求 {i} 的特征“{NAME[k]}”未在发明内容中出现")
    for v in re.findall(r"\d+(?:\.\d+)?\s?m(?![a-zA-Z])", c["text"]):
        if v not in content:
            bad(f"权利要求 {i} 的数值“{v}”未在发明内容中出现")
for key in ("浮动铰接件", "外部可触测基准点", "高度读数基准面", "中立位姿", "锥形凹坑", "横向倾角"):
    if key not in impl:
        bad(f"具体实施方式未说明“{key}”")
for eqn in ("（1）", "（2）", "（3）", "（4）"):
    if f"式{eqn}" not in impl:
        bad(f"具体实施方式未引用式{eqn}")

# ------------------------------------------------------------------ 7 算例复算
q0x, q0z, d0x, d0z, c0 = 75.0, 35.0, -174.09, 134.00, 1316.0
_MDF = os.path.join(ROOT, "仿真验证", "数据", "model_data.json")
if os.path.exists(_MDF):          # 版本目录带模型数据时，d0 取模型中 43 相对球心 O 的坐标（两位小数，与说明书一致）
    _p43 = json.load(open(_MDF, encoding="utf-8"))["points"]["P43"]
    d0x, d0z = round(_p43[0] - 707.0, 2), round(_p43[2] - 915.0, 2)
    if f"(−{abs(d0x):.2f}, 0, {d0z:.2f})" not in impl:
        bad(f"说明书中的 d0 与模型不一致（模型 d0=({d0x:.2f}, 0, {d0z:.2f})）")
notes.append(f"算例常矢量 q0=({q0x:g}, 0, {q0z:g})，d0=({d0x:.2f}, 0, {d0z:.2f})，c={c0:g}")


def D(A, L, H, psi, eps):
    A, psi, eps = map(math.radians, (A, psi, eps))
    s1 = (L * math.cos(A), L * math.sin(A), H - c0)
    vx = d0x * math.cos(eps) - d0z * math.sin(eps)
    vz = d0x * math.sin(eps) + d0z * math.cos(eps)
    s2 = (q0x * math.cos(A) + vx * math.cos(psi), q0x * math.sin(A) + vx * math.sin(psi), q0z + vz)
    d = tuple(a + b for a, b in zip(s1, s2))
    return s1, s2, d, (vx, vz)


def fmt(v):
    return "(" + ", ".join(("0" if abs(x) < 0.005 else f"{x:.2f}".replace("-", "−")) for x in v) + ")"


cases = [(0, 632, 30, 0, 20), (0, 632, 30, 60, 10), (0, 632, 42, 0, 20), (35, 632, 30, 70, 20)]
flat = impl.replace(" ", "").replace(",", ", ")
for cs in cases:
    s1, s2, d, _ = D(*cs)
    for lab_, v in (("S1", s1), ("S2", s2), ("D", d)):
        f = fmt(v).replace(" ", "")
        # 文本中 0 分量写作“0”，其余两位小数
        f2 = f.replace("(0.00", "(0").replace(",0.00", ",0")
        if f.replace(",", ", ") not in flat and f2.replace(",", ", ") not in flat:
            if f not in impl.replace(" ", "") and f2 not in impl.replace(" ", ""):
                bad(f"算例 {cs} 的 {lab_}={fmt(v)} 未在文中找到（请核对）")
    mag = f"|D|={math.sqrt(sum(x * x for x in d)):.1f}"
    notes.append(f"算例 {cs}: D={fmt(d)} {mag}")
d1, d2 = D(*cases[0])[2], D(*cases[1])[2]
dd = math.dist(d1, d2)
if f"{dd:.1f}" not in impl:
    bad(f"重新指向前后偏置量变化 {dd:.1f} 未在文中找到")

# ------------------------------------------------------------------ 8 仿真数值（修订版）
SIMD = os.path.join(ROOT, "仿真验证", "数据")
if os.path.isdir(SIMD):
    SS = json.load(open(os.path.join(SIMD, "sim_structural.json"), encoding="utf-8"))
    SO = json.load(open(os.path.join(SIMD, "sim_offset.json"), encoding="utf-8"))
    full = " ".join(d["text"] for d in desc)
    want = {
        "仿真一 本发明平均误差": "%.2f" % SO["仿真一"]["M2"]["三维误差mm"]["均值"],
        "仿真一 全站仪重测平均": "%.2f" % SO["仿真一"]["M1"]["三维误差mm"]["均值"],
        "仿真一 沿用平均": "%.0f" % SO["仿真一"]["M0"]["三维误差mm"]["均值"],
        "仿真一 棱镜靶标重测平均": "%.2f" % SO["仿真一"]["M1b"]["三维误差mm"]["均值"],
        "仿真一 本发明变化量平均": "%.2f" % SO["仿真一"]["M2"]["调姿前后变化量误差mm"]["均值"],
        **({"仿真一 自动采集平均": "%.2f" % SO["仿真一"]["M2a"]["三维误差mm"]["均值"]} if "M2a" in SO["仿真一"] else {}),
        **({"仿真二 立杆临界风速": "%.1f" % SS["仿真二"]["涡激振动"][0]["临界风速m/s"]} if "涡激_阻尼器" in SS["仿真二"] else {}),
        "仿真二 43风致(本发明)": "%.2f" % SS["仿真二"]["K2"]["极限风况包络"]["43风致位移mm"],
        "仿真二 43风致(悬挑)": "%.2f" % SS["仿真二"]["CANT"]["极限风况包络"]["43风致位移mm"],
        "仿真二 43风致(加强悬挑)": "%.2f" % SS["仿真二"]["CANTb"]["极限风况包络"]["43风致位移mm"],
        "仿真二 角反射器风力": "%.1f" % SS["仿真二"]["K2"]["极限风况包络"]["角反射器风力N"],
        "仿真二 锁紧安全系数": "%.1f" % SS["仿真二"]["锁紧校核"]["安全系数"],
        "仿真二 主导频率": "%.1f" % SS["仿真二"]["K2"]["角反射器主导振型Hz"],
        "仿真三 每mm竖向力": "%.0f" % SS["仿真三"]["K1"]["每1mm差异位移"]["铰接竖向力N"],
        "仿真三 直接固接每mm竖向力": "%.0f" % SS["仿真三"]["K1b"]["每1mm差异位移"]["铰接竖向力N"],
        "仿真三 粘着刚度": "%.0f" % SS["仿真三"]["粘滑摩擦"]["粘着竖向刚度N/mm"],
        "仿真四 一次测定RMS": "%.2f" % SO["仿真四"]["现有做法（一次测定）"]["均方根"],
        "仿真四 按月RMS": "%.2f" % SO["仿真四"]["本发明按月人工读H"]["均方根"],
    }
    for k, v in want.items():
        if v not in full:
            bad(f"{k} 的仿真值 {v} 未在说明书中找到")
    for k in ("表1", "表2", "表3", "表4", "表5"):
        if not any(d["type"] == "table" and d["text"].startswith(k) for d in desc):
            bad(f"缺少{k}")
        if f"{k}" not in impl.replace(" ", "") and not re.search(k + r"(?!\d)", full):
            bad(f"正文未引用{k}")
    notes.append("仿真数值与 仿真验证/数据 一致（%d 项）" % len(want))
    for k in ("文献1", "文献2", "文献3", "文献4"):
        if k not in background:
            bad(f"背景技术缺少{k}")

# ------------------------------------------------------------------ 结果
lines = [n for n in notes if n] + ["-" * 60]
if problems:
    lines.append(f"发现 {len(problems)} 个问题：")
    lines += ["  ✗ " + p for p in problems]
else:
    lines.append("全部检查通过 ✓")
report = "\n".join(lines)
with open(os.path.join(ROOT, "申请文件", "_校验报告.txt"), "w", encoding="utf-8") as fh:
    fh.write(report + "\n")
print(report)
sys.exit(1 if problems else 0)
