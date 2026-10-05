# -*- coding: utf-8 -*-
"""通用发明专利申请文件一致性校验（读取 <root>/07_申请文件/_expanded.json）。

用法：.venv\\Scripts\\python.exe check_patent.py --root <专利文件夹> [--min-figs 12] [--min-claims 15]
检查项：
  1 摘要 ≤300 字、含发明名称、摘要中标记均在摘要附图中；
  2 禁用词与未展开记号（实用新型、如权利要求、TODO、【待填、{、}、** 等）；
  3 权利要求：编号连续、仅一个句号、引用在前、独权以“一种”开头、从权含“其特征在于”、
    “所述X（k）”有引用基础、多项从属择一且不以多项从属为基础、独权类型（方法/系统/装置/介质）齐全；
  4 说明书五部分顺序、段号连续、背景技术无附图标记、全部标记在具体实施方式以“名称+标记”出现、
    附图标记说明与标记表一致；
  5 附图：附图说明含“图N为”、具体实施方式引用每幅图、每幅图标记均有文字说明；
  6 支持：权利要求中的部件名称在发明内容出现；
  7 数据一致：08_脚本/checks.json 中列出的仿真数值字符串必须在说明书中出现（数值由仿真 JSON 生成）。
结果写入 <root>/07_申请文件/_校验报告.txt；有问题时退出码 1。
"""
import argparse
import json
import os
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--min-figs", type=int, default=12)
ap.add_argument("--min-claims", type=int, default=15)
args = ap.parse_args()
ROOT = os.path.abspath(args.root)
OUT = os.path.join(ROOT, "07_申请文件")
EXP = json.load(open(os.path.join(OUT, "_expanded.json"), encoding="utf-8"))
NUM = json.load(open(os.path.join(ROOT, "08_脚本", "numerals.json"), encoding="utf-8"))
SRC = ""
for f in ("patent_text.js", "patent_desc.js"):
    p = os.path.join(ROOT, "08_脚本", f)
    if os.path.exists(p):
        SRC += "".join(ln for ln in open(p, encoding="utf-8") if not ln.lstrip().startswith("//"))
CHECKS = os.path.join(ROOT, "08_脚本", "checks.json")

USED = EXP["used_labels"]
NAME = {k: NUM[k]["name"] for k in USED}
NFIG = len(EXP["fig_labels"])
problems, notes = [], []
bad = problems.append

# 1 摘要 ------------------------------------------------------------------------------------
ab = EXP["abstract"]
n_ab = len(re.sub(r"\s", "", ab))
notes.append(f"摘要字数 {n_ab}")
if n_ab > 300:
    bad(f"摘要超过 300 字：{n_ab}")
af = str(EXP.get("abstractFigure", 1))
fig_ab = set(EXP["fig_labels"].get("1", []))
for m in re.finditer(r"（(\d+[A-Za-z]?)）", ab):
    k = m.group(1)
    if k not in NAME:
        bad(f"摘要中标记 {k} 不在附图中")
    elif not ab[:m.start()].endswith(NAME[k]):
        bad(f"摘要中标记 {k} 前的名称不是“{NAME[k]}”")
title_core = EXP["title"].replace("一种", "", 1)
if title_core[:12] not in ab:
    bad("摘要未包含发明名称")

# 2 禁用词 ----------------------------------------------------------------------------------
alltext = ab + "".join(c["text"] for c in EXP["claims"]) + "".join(d["text"] for d in EXP["description"])
for w in ("实用新型", "如权利要求", "TODO", "XXX", "【待填", "待填", "{", "}", "**", "undefined", "NaN"):
    if w in alltext:
        bad(f"出现禁用词或未展开记号：{w}")

# 3 权利要求 --------------------------------------------------------------------------------
claims = EXP["claims"]
if len(claims) < args.min_claims:
    bad(f"权利要求仅 {len(claims)} 项（要求 ≥{args.min_claims}）")
deps = {}
for i, c in enumerate(claims, 1):
    t = c["text"]
    if c["no"] != i or not t.startswith(f"{i}. "):
        bad(f"权利要求编号不连续：{c['no']}")
    if not t.endswith("。") or t.count("。") != 1:
        bad(f"权利要求 {i} 应以且仅以一个句号结束（句号数 {t.count('。')}）")
    head = t.split("其特征在于")[0]
    refs = [int(x) for x in re.findall(r"权利要求(\d+)", head)]
    for a, b2 in re.findall(r"权利要求(\d+)至(\d+)", head):
        refs += list(range(int(a), int(b2) + 1))
    refs += [int(x) for x in re.findall(r"(?:或|、)(\d+)", head) if "权利要求" in head]
    for r in refs:
        if r >= i:
            bad(f"权利要求 {i} 引用了在后的权利要求 {r}")
    deps[i] = sorted(set(refs))
    body = t[len(f"{i}. "):]
    is_indep = body.startswith("一种")
    if not refs and not is_indep:
        bad(f"独立权利要求 {i} 应以“一种”开头")
    if refs and not is_indep and "其特征在于" not in t:
        bad(f"从属权利要求 {i} 缺少“其特征在于”")
    for m in re.finditer(r"（(\d+[A-Za-z]?)）", t):
        k = m.group(1)
        if k not in NAME:
            bad(f"权利要求 {i} 中标记 {k} 不在附图中")
        elif not t[:m.start()].endswith(NAME[k]):
            bad(f"权利要求 {i} 中标记 {k} 前的名称不是“{NAME[k]}”")


def ancestors(i, seen=None):
    seen = seen if seen is not None else set()
    for r in deps[i]:
        if r not in seen and r in deps:
            seen.add(r)
            ancestors(r, seen)
    return seen


intro = {}
for i, c in enumerate(claims, 1):
    t = c["text"]
    have = set()
    for a in ancestors(i):
        have |= intro.get(a, set())
    for m in re.finditer(r"（(\d+[A-Za-z]?)）", t):
        k = m.group(1)
        if k not in NAME:
            continue
        pre = t[:m.start() - len(NAME[k])]
        if pre.endswith("所述") and k not in have:
            bad(f"权利要求 {i}：“所述{NAME[k]}（{k}）”缺少引用基础")
        have.add(k)
    intro[i] = have
indep = [i for i, c in enumerate(claims, 1) if c["text"][len(f'{i}. '):].startswith("一种")]
notes.append(f"权利要求 {len(claims)} 项；独立权利要求：{indep}")
kinds = {"方法": False, "系统或装置": False, "介质或设备": False}
for i in indep:
    t = claims[i - 1]["text"]
    lead = t.split("，")[0]
    if "方法" in lead:
        kinds["方法"] = True
    if any(w in lead for w in ("系统", "装置", "载荷", "反射器", "节点", "设备", "测振站", "站")):
        kinds["系统或装置"] = True
    if any(w in lead for w in ("存储介质", "电子设备")):
        kinds["介质或设备"] = True
for k, v in kinds.items():
    if not v:
        bad(f"缺少{k}类独立权利要求")
multi = [i for i in deps if i not in indep and len(deps[i]) > 1]
for i in multi:
    if "或" not in claims[i - 1]["text"].split("所述")[0] and "至" not in claims[i - 1]["text"].split("所述")[0]:
        bad(f"多项从属权利要求 {i} 未以择一方式引用")
    for r in deps[i]:
        if r in multi:
            bad(f"多项从属权利要求 {i} 以多项从属权利要求 {r} 为基础")

# 4 说明书 ----------------------------------------------------------------------------------
desc = EXP["description"]
heads = [d["text"] for d in desc if d["type"] == "h"]
if heads != ["技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式"]:
    bad(f"说明书部分标题顺序不对：{heads}")
nos = [int(d["no"][1:-1]) for d in desc if d.get("no")]
if nos != list(range(1, len(nos) + 1)):
    bad("段号不连续")
nchar = sum(len(d["text"]) for d in desc)
notes.append(f"说明书段落 {len(nos)} 段，约 {nchar} 字")


def part(p):
    return " ".join(d["text"] for d in desc if d.get("part") == p and d["type"] != "labels")


impl, content, figdesc = part("具体实施方式"), part("发明内容"), part("附图说明")
background = part("背景技术") + part("技术领域")
for k in USED:
    if re.search(re.escape(NAME[k]) + re.escape(k) + r"(?!\d)", background):
        bad(f"背景技术中出现附图标记 {k}")
missing = [k for k in USED if not re.search(re.escape(NAME[k]) + re.escape(k) + r"(?![\d])", impl)]
if missing:
    bad(f"具体实施方式未出现的附图标记：{missing}")
else:
    notes.append(f"附图标记 {len(USED)} 个，均在具体实施方式中出现")
for k in USED:
    for m in re.finditer(re.escape(NAME[k]) + r"[（(]?" + re.escape(k) + r"(?!\d)", SRC):
        bad(f"文本源中手写了附图标记：{SRC[m.start():m.end() + 2]}")
lab = " ".join(d["text"] for d in desc if d["type"] == "labels")
for k in USED:
    if f"{k}、{NAME[k]}" not in lab:
        bad(f"附图标记说明缺少 {k}、{NAME[k]}")

# 5 附图 ------------------------------------------------------------------------------------
if NFIG < args.min_figs:
    bad(f"附图仅 {NFIG} 幅（要求 ≥{args.min_figs}）")
for n in range(1, NFIG + 1):
    if not re.search(rf"图{n}为", figdesc):
        bad(f"附图说明缺少“图{n}为”")
    covered = re.search(rf"图{n}(?!\d)", impl) or any(int(a) <= n <= int(b) for a, b in re.findall(r"图(\d+)至图(\d+)", impl))
    if not covered:
        bad(f"具体实施方式未引用图{n}")
    for k in EXP["fig_labels"][str(n)]:
        if not re.search(re.escape(NAME[k]) + re.escape(k) + r"(?!\d)", impl):
            bad(f"图{n} 中标记 {k} 未在具体实施方式中说明")
notes.append(f"附图 {NFIG} 幅")

# 6 支持 ------------------------------------------------------------------------------------
for i, c in enumerate(claims, 1):
    for k in c["nums"]:
        if NAME[k] not in content and NAME[k] not in impl:
            bad(f"权利要求 {i} 的特征“{NAME[k]}”未在说明书中出现")

# 7 数据一致 --------------------------------------------------------------------------------
full = " ".join(d["text"] for d in desc)
if os.path.exists(CHECKS):
    ck = json.load(open(CHECKS, encoding="utf-8"))
    nok = 0
    for item in ck:
        if str(item["value"]) not in full:
            bad(f"仿真数值 {item['name']}={item['value']} 未在说明书中找到")
        else:
            nok += 1
    notes.append(f"仿真数值与数据文件一致 {nok}/{len(ck)} 项")
else:
    notes.append("未提供 checks.json（跳过仿真数值一致性）")

lines = [n for n in notes if n] + ["-" * 60]
if problems:
    lines.append(f"发现 {len(problems)} 个问题：")
    lines += ["  ✗ " + p for p in problems]
else:
    lines.append("全部检查通过 ✓")
report = "\n".join(lines)
with open(os.path.join(OUT, "_校验报告.txt"), "w", encoding="utf-8") as fh:
    fh.write(report + "\n")
sys.stdout.reconfigure(encoding="utf-8")
print(report)
sys.exit(1 if problems else 0)
