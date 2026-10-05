# -*- coding: utf-8 -*-
"""V1-5 专利附图（图16~18，任务书称“附图11~13”，实际文件编号为 16~18）曲线数据核对：
从 SVG 反解曲线坐标（按刻度标定像素→数据），与 C 的 JSON 数据逐点比较。"""
import json, os, re, math
import numpy as np
from v1_common import SIM, dump

FIG = os.path.join(SIM, "图", "专利附图")
J = lambda n: json.load(open(os.path.join(SIM, "数据", n + ".json"), encoding="utf-8"))


def svg_lines(name):
    s = open(os.path.join(FIG, name + ".svg"), encoding="utf-8").read()
    lines = []
    for m in re.finditer(r'<g id="line2d_\d+">\s*<path d="([^"]+)"\s*clip-path', s):
        pts = re.findall(r"[ML] ([\d.\-]+) ([\d.\-]+)", m.group(1))
        lines.append(np.array([[float(a), float(b)] for a, b in pts]))
    ticks = {}
    for ax in ("x", "y"):
        ticks[ax] = []
        # v1.1：刻度值从 SVG 刻度文字读取（不再写死），图16 曲线随主仿真修正后刻度会变化
        for m in re.finditer(r'<g id="%stick_\d+">(.*?)</text>' % ax, s, re.S):
            u = re.search(r'<use [^>]*x="([\d.]+)" y="([\d.]+)"', m.group(1))
            v = re.search(r'>([^<>]*)$', m.group(1)).group(1).replace("−", "-")
            try:
                val = float(v)
            except ValueError:
                val = None
            ticks[ax].append((float(u.group(1)), float(u.group(2)), val))
    txt = re.findall(r"<text [^>]*>([^<]+)", s)
    return lines, ticks, txt


def lin_map(pix, vals):
    a, b = np.polyfit(pix, vals, 1)
    return lambda p: a * np.asarray(p) + b


def compare(curve_px, fx, fy, xd, yd, logy=False):
    x = fx(curve_px[:, 0]); y = fy(curve_px[:, 1])
    if logy:
        y = 10 ** y
    yi = np.interp(x, xd, yd)
    err = np.abs(y - yi)
    return {"点数": len(x), "最大绝对偏差": float(err.max()), "相对偏差%": float(100 * err.max() / np.max(np.abs(yd))),
            "曲线终值(图)": float(y[-1]), "终值(JSON)": float(yd[-1]), "曲线最大(图)": float(y.max()), "最大(JSON)": float(np.max(yd))}


R = {}
# 图16
lines, tk, _ = svg_lines("图16")
data = [l for l in lines if len(l) > 10]
fx = lin_map([p[0] for p in tk["x"]], [p[2] for p in tk["x"]])
fy = lin_map([p[1] for p in tk["y"]], [p[2] for p in tk["y"]])
sc = J("scen")["时程"]["C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"]
R["图16"] = {}
for c, s in zip(data, ("M1s", "M1b", "M2")):
    o = sc[s]
    R["图16"][s] = compare(c, fx, fy, np.array(o["t"]) / 60, np.array(o["F_N"]) / 1e3)
R["图16"]["推力带线kN"] = [float(fy(l[0, 1])) for l in lines if len(l) == 2]
# 图17
lines, tk, _ = svg_lines("图17")
data = [l for l in lines if len(l) > 10]
fx = lin_map([p[0] for p in tk["x"]], [p[2] for p in tk["x"]])
fy = lin_map([p[1] for p in tk["y"]], [p[2] for p in tk["y"]])
st = J("stiff")
R["图17"] = {}
for c, s in zip(data, ("M1s", "M2S", "M2")):
    R["图17"][s] = compare(c, fx, fy, np.array(st["伸出量mm"]), np.array(st["静刚度N_um"][s]))
# 图18（对数 y，ylim 0.5~400，轴框 y=261.6~10.8）
lines, tk, _ = svg_lines("图18")
data = [l for l in lines if len(l) > 10]
fx = lin_map([p[0] for p in tk["x"]], [p[2] for p in tk["x"]])
fy = lin_map([261.6, 10.8], [math.log10(0.5), math.log10(400)])
en = J("energy")
R["图18"] = {}
for c, s in zip(data, ("M0", "M1s", "M2")):
    E = en["单件循环"][s]["单件电能kWh"] * 1e3
    x = fx(c[:, 0]); y = 10 ** fy(c[:, 1])
    R["图18"][s] = {"终值(图)Wh": float(y[-1]), "单件电能(JSON)Wh": E, "相对偏差%": 100 * (y[-1] / E - 1),
                    "终点时间min": float(x[-1]), "循环时间min": 655.8 / 60}
dump("v1_figcheck", R)
print(json.dumps(R, ensure_ascii=False, indent=1))
