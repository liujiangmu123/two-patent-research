# -*- coding: utf-8 -*-
"""由申请文件 _expanded.json 生成技术交底书（供代理师撰写/核对用）。
用法：.venv\\Scripts\\python.exe 00_工具\\make_disclosure.py <专利包根目录> [--type 发明|实用新型] [--extra 补充说明.md]
输出：<根>\\08_技术交底书\\技术交底书.md（随后用 reports_to_docx.ps1 转 docx/pdf）。
内容全部取自申请文件与本件查新、校核/仿真报告的结论段，不另编数值。"""
import json
import os
import re
import sys
import argparse

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--type", default="发明")
ap.add_argument("--extra", default="")
a = ap.parse_args()
ROOT = os.path.abspath(a.root)
E = json.load(open(os.path.join(ROOT, "06_申请文件", "_expanded.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "08_技术交底书")
os.makedirs(OUT, exist_ok=True)

parts = {}
cur = None
for d in E["description"]:
    if d.get("type") == "h":
        cur = d["text"]
        parts[cur] = []
    elif cur is not None and d.get("type") != "labels":
        parts[cur].append(d["text"])


def sect(key):
    for k, v in parts.items():
        if key in k:
            return v
    return []


L = []
L.append(f"# 技术交底书：{E['title']}")
L.append("")
L.append("| 项目 | 内容 |")
L.append("| --- | --- |")
L.append(f"| 申请类型 | {a.type}专利 |")
L.append("| 申请人 | 兰州石化职业技术大学 |")
L.append("| 发明人 | 车永昌、汪洋 |")
L.append("| 项目来源 | 甘肃省科技计划项目（自然科学基金）24JRRA1144 |")
L.append("| 同日申请 | 本件属于 5 件同日申请组合之一，组合边界见 `车老师专利/00_专利组合总览.md` |")
L.append(f"| 权利要求 | {len(E['claims'])} 项；独立权利要求：{'、'.join(str(c['no']) for c in E['claims'] if '根据权利要求' not in c['text'][:12])} |")
L.append(f"| 附图 | {len(E['figures'])} 幅；附图标记 {len(E.get('used_labels', []))} 个 |")
L.append("")
L.append("## 1 技术领域")
L += sect("技术领域") + [""]
L.append("## 2 背景技术与现有技术的不足")
L += sect("背景技术") + [""]
cont = sect("内容")
L.append("## 3 要解决的技术问题、技术方案与有益效果")
L += cont + [""]
L.append("## 4 附图说明")
L += sect("附图说明") + [""]
L.append("## 5 具体实施方式（摘要，全文见申请文件说明书）")
emb = sect("具体实施方式")
L += emb + [""]
L.append("## 6 拟要求保护的范围（权利要求书全文）")
for c in E["claims"]:
    L.append(c["text"])
    L.append("")
L.append("## 7 说明书摘要")
L.append(E["abstract"])
L.append("")
if a.extra and os.path.exists(a.extra):
    L.append(open(a.extra, encoding="utf-8").read())
L.append("## 8 需要申请人和代理师关注的事项")
iss = os.path.join(ROOT, "10_审查与迭代", "未关闭问题清单.md")
if os.path.exists(iss):
    txt = open(iss, encoding="utf-8").read()
    txt = re.sub(r"^# .*\n", "", txt)
    L.append(txt)
else:
    L.append("见 `10_审查与迭代/未关闭问题清单.md`。")
s = "\n".join(L)
s = s.replace("<", "＜").replace(">", "＞") if False else s
open(os.path.join(OUT, "技术交底书.md"), "w", encoding="utf-8").write(s)
print("写出", os.path.join(OUT, "技术交底书.md"), len(s), "字符")
