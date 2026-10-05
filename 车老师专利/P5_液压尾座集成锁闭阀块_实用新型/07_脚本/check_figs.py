# -*- coding: utf-8 -*-
r"""P5 附图检查：彩色像素、标记齐全、引线交叉、落点、标注版与无标注版成对、PNG 分辨率；并生成 05_附图/附图_清单.md。

用法：.venv\Scripts\python.exe 07_脚本\check_figs.py
输出：05_附图/_附图检查.json、05_附图/附图_清单.md；有问题时退出码 1。
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "05_附图")
NUMS = {k: v for k, v in json.load(open(os.path.join(FIG, "numerals.json"), encoding="utf-8")).items() if not k.startswith("_")}
TITLES = {1: "尾座液压缸与集成锁闭阀块的装配剖视图（沿缸轴线所在竖直平面剖开）", 2: "集成锁闭阀块的轴测图",
          3: "集成锁闭阀块的主视图", 4: "集成锁闭阀块的后视图", 5: "沿泄放阀孔轴线、垂直于缸轴线剖开的剖视图",
          6: "沿安全阀孔轴线、垂直于缸轴线剖开的剖视图", 7: "图1 中第一锁闭阀孔与油温传感器套管附近的局部放大图",
          8: "图1 中第二锁闭阀孔与第二测压孔附近的局部放大图"}


def main():
    probs, rows, used = [], [], {}
    ids = sorted(int(f[1:-5]) for f in os.listdir(os.path.join(FIG, "标注版")) if f.startswith("图") and f.endswith(".json"))
    for i in ids:
        jf = os.path.join(FIG, "标注版", "图%d.json" % i)
        r = json.load(open(jf, encoding="utf-8"))
        item = {"图": i}
        for ver in ("标注版", "无标注版"):
            for ext in ("png", "svg"):
                p = os.path.join(FIG, ver, "图%d.%s" % (i, ext))
                if not os.path.exists(p):
                    probs.append("图%d %s 缺 %s" % (i, ver, ext))
            p = os.path.join(FIG, ver, "图%d.png" % i)
            if os.path.exists(p):
                im = Image.open(p)
                dpi = im.info.get("dpi", (0, 0))
                a = np.asarray(im.convert("RGB")).astype(int)
                col = int((np.abs(a[..., 0] - a[..., 1]) + np.abs(a[..., 1] - a[..., 2]) > 6).sum())
                item[ver] = {"px": list(im.size), "dpi": [round(float(d)) for d in dpi], "彩色像素": col}
                if col:
                    probs.append("图%d %s 有彩色像素 %d" % (i, ver, col))
                if round(float(dpi[0])) < 395:
                    probs.append("图%d %s 分辨率 %s dpi" % (i, ver, dpi))
        if r.get("missing"):
            probs.append("图%d 缺标注 %s" % (i, r["missing"]))
        if r.get("crossings"):
            probs.append("图%d 引线交叉 %d" % (i, r["crossings"]))
        if not r.get("all_anchors_ok"):
            probs.append("图%d 落点未落在所标零件上" % i)
        for n in r["labels"]:
            if n not in NUMS:
                probs.append("图%d 标记 %s 不在 numerals.json" % (i, n))
            used.setdefault(n, []).append(i)
        item.update({"标记": r["labels"], "比例": r["scale"], "印刷尺寸_mm": r["size_mm"], "引线交叉": r["crossings"],
                     "引线最小掠过距离_mm": r["min_leader_pass_mm"]})
        rows.append(item)
    unused = [n for n in NUMS if n not in used]
    if unused:
        probs.append("numerals.json 中未出现在任何附图的标记：%s" % unused)
    rep = {"图数": len(ids), "问题": probs, "逐图": rows, "标记出现位置": used}
    with open(os.path.join(FIG, "_附图检查.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    L = ["# P5 附图清单", "", "由 `07_脚本/check_figs.py` 生成。附图由 `07_脚本/p5_figs.py` 从 `04_模型/P5_出图模型.FCStd`（FreeCAD 1.1，无头）投影得到，"
         "黑白线条，图中只有附图标记；`标注版/` 用于申请文件，`无标注版/` 几何与比例相同、只去掉标号与引线。每图 PNG（400 dpi）+ SVG + JSON（标记、落点、引线检查）。", "",
         "| 图 | 内容 | 印刷尺寸 mm | 附图标记 |", "|---|---|---|---|"]
    for it in rows:
        L.append("| 图%d | %s | %s×%s | %s |" % (it["图"], TITLES.get(it["图"], ""), it["印刷尺寸_mm"][0], it["印刷尺寸_mm"][1],
                                             "、".join(it["标记"])))
    L += ["", "## 附图标记表", "", "| 标记 | 名称 | 出现于 |", "|---|---|---|"]
    for n in sorted(NUMS, key=lambda x: int(x)):
        L.append("| %s | %s | %s |" % (n, NUMS[n]["name"], "、".join("图%d" % k for k in used.get(n, []))))
    L += ["", "## 检查结果", ""]
    L += ["- 问题：%s" % ("无" if not probs else "；".join(probs)),
          "- 每图彩色像素数均为 0、PNG 400 dpi、引线交叉 0、零件落点全部落在所标零件可见区域内（见 `_附图检查.json`）。" if not probs else "- 见上"]
    L += ["", "## 说明", "",
          "- 剖面线：阀块本体 45°/1.5 mm；端盖 135°/1.5 mm；缸筒 135°/2.6 mm；活塞 45°/2.6 mm；活塞杆横截面 135°/1.0 mm；套管、螺塞细密线；O 形圈与密封件用密交叉线近似涂黑。",
          "- 外购件（插装阀、传感器、测压排气接头）、标准紧固件和纵剖时的活塞杆按制图惯例不剖。",
          "- 图5、图6 为简化表达：剖切面后方的其他插装阀与接头省略未画。",
          "- 插装阀、传感器为简化外形，内部结构未表达（不属于本实用新型的改进点）。"]
    with open(os.path.join(FIG, "附图_清单.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("图数", len(ids), "问题", probs or "无")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
