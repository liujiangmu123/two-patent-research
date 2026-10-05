# -*- coding: utf-8 -*-
"""原理类专利附图（图1~图6）生成脚本，子任务 D1。
黑白线条，液压符号按 GB/T 786.1 简化绘制。输出：05_附图/标注版、05_附图/无标注版（PNG 400dpi + SVG + 图N.json）。
运行：.venv\\Scripts\\python.exe 07_脚本\\schematic_figs.py
"""
import json, os, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, FancyBboxPatch, Ellipse, Arc
import numpy as np

plt.rcParams["font.sans-serif"] = ["SimSun", "SimHei"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "path"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "05_附图")
NUM = json.load(open(os.path.join(OUT, "numerals.json"), encoding="utf-8"))
LW, LWT, FS = 0.9, 0.55, 8.5

class D:
    """一张附图的画布。坐标单位 = 图纸 mm。"""
    def __init__(self, w, h, labeled):
        self.w, self.h, self.labeled = w, h, labeled
        self.fig = plt.figure(figsize=(w / 25.4, h / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w); self.ax.set_ylim(0, h); self.ax.axis("off")
        self.labels, self.segs = [], []
    # 基本图元
    def L(self, pts, lw=LW, ls="-"):
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color="k", lw=lw, ls=ls, solid_capstyle="butt",
                     dashes=(4, 2) if ls == "--" else (None if ls == "-" else (1, 1.5)) or (None,))
    def line(self, pts, lw=LW): self.ax.plot(*zip(*pts), color="k", lw=lw)
    def dash(self, pts, lw=LWT): self.ax.plot(*zip(*pts), color="k", lw=lw, ls=(0, (4, 2)))
    def rect(self, x, y, w, h, lw=LW, ls="-", fc="none"):
        self.ax.add_patch(Rectangle((x, y), w, h, fill=fc != "none", fc=fc, ec="k", lw=lw,
                                    ls=ls if ls == "-" else (0, (5, 2))))
    def circ(self, x, y, r, lw=LW, fc="none"):
        self.ax.add_patch(Circle((x, y), r, fill=fc != "none", fc=fc, ec="k", lw=lw))
    def tri(self, pts, fill=True): self.ax.add_patch(Polygon(pts, closed=True, fc="k" if fill else "none", ec="k", lw=LWT))
    def dot(self, x, y, r=0.6): self.circ(x, y, r, lw=0.3, fc="k")
    def text(self, x, y, s, fs=FS, **kw):
        kw.setdefault("ha", "center"); kw.setdefault("va", "center")
        self.ax.text(x, y, s, fontsize=fs, **kw)
    def arrow(self, x0, y0, x1, y1, lw=LWT, head=1.6):
        self.line([(x0, y0), (x1, y1)], lw)
        a = math.atan2(y1 - y0, x1 - x0)
        p = [(x1, y1), (x1 - head * math.cos(a) + head * .4 * math.sin(a), y1 - head * math.sin(a) - head * .4 * math.cos(a)),
             (x1 - head * math.cos(a) - head * .4 * math.sin(a), y1 - head * math.sin(a) + head * .4 * math.cos(a))]
        self.tri(p)
    def spring(self, x0, y0, x1, y1, n=4, amp=1.0):
        t = np.linspace(0, 1, 2 * n + 1)
        dx, dy = x1 - x0, y1 - y0; l = math.hypot(dx, dy); nx, ny = -dy / l, dx / l
        pts = [(x0 + dx * s + (amp * nx * (1 if i % 2 else -1) if 0 < i < 2 * n else 0),
                y0 + dy * s + (amp * ny * (1 if i % 2 else -1) if 0 < i < 2 * n else 0)) for i, s in enumerate(t)]
        self.line(pts, LWT)
    def lab(self, num, ax_, ay, tx, ty):
        """附图标记：引线细实线，末端小圆点。无标注版不画。"""
        num = str(num)
        if num not in self.labels: self.labels.append(num)
        if not self.labeled: return
        self.dot(ax_, ay, 0.45)
        self.line([(ax_, ay), (tx, ty)], 0.4)
        self.segs.append(((ax_, ay), (tx, ty)))
        ha = "left" if tx >= ax_ else "right"
        self.text(tx + (0.6 if ha == "left" else -0.6), ty, num, fs=FS, ha=ha)
    def title(self, s):
        self.text(self.w / 2, 3.5, s, fs=10.5)
    def save(self, n, title):
        sub = "标注版" if self.labeled else "无标注版"
        d = os.path.join(OUT, sub); os.makedirs(d, exist_ok=True)
        base = os.path.join(d, f"图{n}")
        self.fig.savefig(base + ".png", dpi=400, facecolor="white")
        self.fig.savefig(base + ".svg", facecolor="white")
        plt.close(self.fig)
        info = {"fig": n, "title": title, "size_mm": [self.w, self.h], "labeled": self.labeled,
                "labels": sorted(self.labels, key=lambda s: (len(s), s)) if self.labeled else [],
                "labels_in_figure_body": sorted(self.labels, key=lambda s: (len(s), s)),
                "names": {k: NUM.get(k, {}).get("name", "") for k in self.labels},
                "missing": [k for k in self.labels if k not in NUM],
                "crossings": count_cross(self.segs) if self.labeled else 0}
        json.dump(info, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return info

def count_cross(segs):
    def ccw(a, b, c): return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])
    n = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i]; c, d = segs[j]
            if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0: n += 1
    return n

# ---------------- 液压符号（GB/T 786.1 简化） ----------------
def tank(d, x, y):
    d.line([(x - 3, y + 2.2), (x - 3, y), (x + 3, y), (x + 3, y + 2.2)])
def tank_line(d, x, y_from):
    d.line([(x, y_from), (x, y_from - 3)]); tank(d, x, y_from - 5)
def pump(d, x, y, r=4):
    d.circ(x, y, r); d.tri([(x, y + r), (x - 1.5, y + r - 2.4), (x + 1.5, y + r - 2.4)])
def motor(d, x, y, r=4):
    d.circ(x, y, r); d.text(x, y, "M", fs=8)
def filt(d, x, y, s=3.2):
    d.ax.add_patch(Polygon([(x, y + s), (x + s, y), (x, y - s), (x - s, y)], closed=True, fc="none", ec="k", lw=LW))
    d.dash([(x - s, y), (x + s, y)])
def check(d, x, y, up=True, s=2.2):
    """单向阀：球 + 阀座，up=True 允许自下而上流动。"""
    sg = 1 if up else -1
    d.circ(x, y, s * 0.7)
    d.line([(x - s, y + sg * s * 1.3), (x, y - sg * s * 0.1), (x + s, y + sg * s * 1.3)], LW)
def check_h(d, x, y, right=True, s=2.2):
    sg = 1 if right else -1
    d.circ(x, y, s * 0.7)
    d.line([(x + sg * s * 1.3, y - s), (x - sg * s * 0.1, y), (x + sg * s * 1.3, y + s)], LW)
def orifice(d, x, y, vertical=True, s=2.6):
    if vertical:
        d.ax.add_patch(Arc((x - 2.2, y), 3, s * 2, theta1=-60, theta2=60, lw=LW))
        d.ax.add_patch(Arc((x + 2.2, y), 3, s * 2, theta1=120, theta2=240, lw=LW))
    else:
        d.ax.add_patch(Arc((x, y - 2.2), s * 2, 3, theta1=30, theta2=150, lw=LW))
        d.ax.add_patch(Arc((x, y + 2.2), s * 2, 3, theta1=210, theta2=330, lw=LW))
def accumulator(d, x, y):
    """蓄能器（气体隔离式）：竖椭圆 + 中间隔离线，下端接口在 (x, y)。"""
    d.ax.add_patch(FancyBboxPatch((x - 3, y + 1.5), 6, 10, boxstyle="round,pad=0,rounding_size=3", fc="none", ec="k", lw=LW))
    d.line([(x - 3, y + 6.5), (x + 3, y + 6.5)], LWT)
    d.tri([(x, y + 11.5), (x - 1.2, y + 9.5), (x + 1.2, y + 9.5)])
    d.line([(x, y), (x, y + 1.5)])
def psensor(d, x, y, side=1):
    """压力传感器：圆 + 内部 P 字代号省略，按 786.1 以圆内斜箭头表示可调/输出电信号。接口在左/右端。"""
    cx = x + side * 4.5
    d.line([(x, y), (cx - side * 2.5, y)], LWT)
    d.circ(cx, y, 2.5, LWT)
    d.line([(cx - 1.5, y - 1.5), (cx + 1.5, y + 1.5)], LWT)
    d.line([(cx + side * 2.5, y), (cx + side * 4.5, y)], LWT); d.line([(cx + side * 4.5, y - 1), (cx + side * 4.5, y + 1)], LWT)
    return cx, y
def tsensor(d, x, y, side=1):
    """温度传感器：圆 + 内部温度计符号。"""
    cx = x + side * 4.5
    d.line([(x, y), (cx - side * 2.5, y)], LWT)
    d.circ(cx, y, 2.5, LWT)
    d.line([(cx, y - 1.0), (cx, y + 1.6)], LWT); d.circ(cx, y - 1.3, 0.55, 0.4, fc="k")
    return cx, y
def relief(d, x, y, vertical=True, w=8, h=10):
    """溢流阀：方框 + 偏置箭头 + 弹簧 + 进口先导虚线。进口在下 (x, y-h/2)，出口在上。"""
    d.rect(x - w / 2, y - h / 2, w, h)
    d.arrow(x + 1.2, y - h / 2, x + 1.2, y + h / 2 - 0.6)
    d.spring(x - w / 2 - 4, y + 2, x - w / 2, y + 2, n=3, amp=0.9)
    d.dash([(x, y - h / 2 - 2.5), (x - w / 2 - 2, y - h / 2 - 2.5), (x - w / 2 - 2, y - 2), (x - w / 2, y - 2)])
    d.tri([(x - w / 2, y - 2), (x - w / 2 - 1.2, y - 1.4), (x - w / 2 - 1.2, y - 2.6)])
def reducer3(d, x, y, w=9, h=11, side=1):
    """三通减压阀（带二次侧溢流）：进口 P 在下、出口 A 在上、溢流口 T 在侧下；出口先导虚线 + 弹簧。"""
    d.rect(x - w / 2, y - h / 2, w, h)
    d.arrow(x - 1.2, y - h / 2, x - 1.2, y + h / 2 - 0.6)          # P→A
    d.arrow(x - 1.2, y + 1.2, x + w / 2 - 2.2, y - h / 2 + 0.6)    # A→T 二次侧溢流
    d.line([(x + w / 2 - 2.2, y - h / 2), (x + w / 2 - 2.2, y - h / 2 - 3)])
    tank(d, x + w / 2 - 2.2, y - h / 2 - 5)
    d.spring(x - w / 2, y - 1.5, x - w / 2 - 4, y - 1.5, n=3, amp=0.9)
    d.line([(x - w / 2 - 4.6, y - 3.5), (x - w / 2 - 3.4, y + 0.6)], LWT)  # 可调斜杠
    d.dash([(x, y + h / 2 + 2.5), (x + w / 2 + 2, y + h / 2 + 2.5), (x + w / 2 + 2, y + 2), (x + w / 2, y + 2)])
    d.tri([(x + w / 2, y + 2), (x + w / 2 + 1.2, y + 2.6), (x + w / 2 + 1.2, y + 1.4)])
def seat22(d, x, y, b=7, flip=False):
    """二位二通常闭电磁座阀（零泄漏）。进出口在竖直方向，(x,y)为工作框中心。
    左框（通电）为通路，右框（常态）为截止并带阀座标识。flip 交换电磁铁与弹簧位置。"""
    xr = x - b / 2  # 右框（常态框）左边
    d.rect(xr, y - b / 2, b, b)          # 常态（截止）框，接口位于此框
    d.rect(xr - b, y - b / 2, b, b)      # 通电框（通路）
    # 常态框：截止（座阀用单向阀座表示零泄漏）
    d.line([(x, y - b / 2), (x, y - 0.6)], LWT); d.line([(x - 1.4, y - 0.6), (x + 1.4, y - 0.6)], LWT)
    d.line([(x, y + b / 2), (x, y + 1.6)], LWT); check(d, x, y + 0.9, up=True, s=1.0)
    # 通电框：通路箭头
    d.arrow(x - b, y - b / 2 + 0.6, x - b, y + b / 2 - 0.6)
    # 电磁铁（左）+ 弹簧（右）
    d.rect(xr - b - 3.2, y - 1.8, 3.2, 3.6, LWT); d.line([(xr - b - 3.2, y - 1.8), (xr - b, y + 1.8)], LWT)
    d.spring(xr + b, y, xr + b + 4, y, n=3, amp=1.0)
    return (x, y - b / 2), (x, y + b / 2)
def dir43(d, x, y, b=8):
    """三位四通电磁换向阀，Y 型中位（P 封闭，A、B、T 连通）。(x,y)为中位框中心，P/T在下，A/B在上。"""
    for k in (-1, 0, 1): d.rect(x + k * b - b / 2, y - b / 2, b, b)
    o = b * 0.28
    xa, xb = x - o, x + o
    # 中位 Y：P 封闭，A、B、T 连通
    d.line([(xa, y + b / 2), (xa, y + 0.5), (xb, y + 0.5), (xb, y + b / 2)], LWT)
    d.line([(xb, y - b / 2), (xb, y + 0.5)], LWT)
    d.line([(xa, y - b / 2), (xa, y - 1.4)], LWT); d.line([(xa - 1.2, y - 1.4), (xa + 1.2, y - 1.4)], LWT)
    # 左位：P→A? 使用平行箭头 P→A、B→T
    cx = x - b
    d.arrow(cx - o, y - b / 2 + .5, cx - o, y + b / 2 - .6); d.arrow(cx + o, y + b / 2 - .5, cx + o, y - b / 2 + .6)
    # 右位：交叉箭头 P→B、A→T
    cx = x + b
    d.arrow(cx - o, y - b / 2 + .5, cx + o, y + b / 2 - .6); d.arrow(cx - o, y + b / 2 - .5, cx + o, y - b / 2 + .6)
    for s in (-1, 1):
        ex = x + s * (1.5 * b)
        d.rect(ex if s > 0 else ex - 3.2, y - 1.8, 3.2, 3.6, LWT)
        d.line([(ex, y - 1.8), (ex + s * 3.2, y + 1.8)], LWT)
        d.spring(ex + s * 3.2, y, ex + s * 6.6, y, n=3, amp=1.0)
    return dict(P=(xa, y - b / 2), T=(xb, y - b / 2), A=(xa, y + b / 2), B=(xb, y + b / 2))
def cylinder(d, x0, y0, L, H, piston_at, rod_out, rod_left=False):
    """双作用单杆缸，水平放置。返回无杆腔、有杆腔接口（下侧）。"""
    d.rect(x0, y0, L, H)
    px = x0 + piston_at
    d.rect(px - 1.2, y0, 2.4, H, LW, fc="k")
    yc = y0 + H / 2
    d.line([(px, yc - 1.2), (x0 + L + rod_out, yc - 1.2)], LW); d.line([(px, yc + 1.2), (x0 + L + rod_out, yc + 1.2)], LW)
    d.line([(x0 + L + rod_out, yc - 1.2), (x0 + L + rod_out, yc + 1.2)], LW)
    return (x0 + 3, y0), (x0 + L - 3, y0)
def pilot_check(d, x, y):
    """液控单向阀：竖直，允许自下而上；先导口虚线由左侧引入。"""
    d.rect(x - 4, y - 4.5, 8, 9, LWT, ls="--")
    check(d, x, y, up=True, s=1.8)
    d.line([(x, y - 4.5), (x, y - 1.2)], LW); d.line([(x, y + 2.3), (x, y + 4.5)], LW)
def rotary_joint(d, x0, x1, y):
    """回转接头：两通道穿过的回转符号（两同心半圆）。"""
    xm = (x0 + x1) / 2
    d.rect(x0 - 4, y - 3.5, x1 - x0 + 8, 7, LW)
    d.ax.add_patch(Arc((xm, y), x1 - x0 + 4, 5, theta1=0, theta2=180, lw=LWT))
    d.ax.add_patch(Arc((xm, y), x1 - x0 + 4, 5, theta1=180, theta2=360, lw=LWT, ls=(0, (2, 1.5))))

# ---------------- 回路 ----------------
def power_unit(d, ox, oy, P_to):
    """动力源 1~9、29。P_to：V0 下游连接终点 x。返回 P 母线 y。"""
    x = ox + 14
    tank(d, x, oy); d.line([(x, oy + 1.5), (x, oy + 8)]); filt(d, x, oy + 11.2)
    d.line([(x, oy + 14.4), (x, oy + 19)]); pump(d, x, oy + 23)
    motor(d, x - 13, oy + 23); d.line([(x - 9, oy + 22.6), (x - 4, oy + 22.6)], LWT); d.line([(x - 9, oy + 23.4), (x - 4, oy + 23.4)], LWT)
    yP = oy + 40
    d.line([(x, oy + 27), (x, yP), (P_to, yP)])
    # 溢流阀 5
    xr = ox + 28; d.dot(xr, yP); d.line([(xr, yP), (xr, yP - 4)]); relief(d, xr, yP - 9)
    d.line([(xr, yP - 14), (xr, yP - 17)]); tank(d, xr, yP - 19)
    # 电磁卸荷阀 6（二位二通常闭）
    xu = ox + 44; d.dot(xu, yP); d.line([(xu, yP), (xu, yP - 6.5)]); seat22(d, xu, yP - 10)
    d.line([(xu, yP - 13.5), (xu, yP - 17)]); tank(d, xu, yP - 19)
    # 单向阀 7
    xc = ox + 56; d.rect(xc - 4, yP - 3.5, 8, 7, 0.01); check_h(d, xc, yP, right=True)
    d.ax.add_patch(Rectangle((xc - 3.2, yP - 0.6), 0.1, 0.1, fc="w", ec="w"))
    # 蓄能器 8，S0 9
    xa = ox + 68; d.dot(xa, yP); d.line([(xa, yP), (xa, yP - 6)])
    d.ax.add_patch(Rectangle((xa - 3.2, yP - 19.5), 6.4, 13.6, fc="none", ec="none"))
    # 蓄能器朝下放置：画在线下方
    d.line([(xa, yP - 6), (xa, yP - 8)])
    accu_down(d, xa, yP - 8)
    xs = ox + 76; d.dot(xs, yP); d.line([(xs, yP), (xs, yP + 5)]);
    d.line([(xs, yP + 5), (xs, yP + 6)], LWT); d.circ(xs, yP + 8.5, 2.5, LWT); d.line([(xs - 1.5, yP + 7), (xs + 1.5, yP + 10)], LWT)
    # 隔离座阀 V0 29（水平管路上，竖向放置的阀用转角接入）
    xv = ox + 90
    d.ax.add_patch(Rectangle((xv - 3, yP - 1), 6, 2, fc="w", ec="w", zorder=3))
    d.line([(xv - 3, yP), (xv - 3, yP - 4.5)]); seat22(d, xv - 3 + 0, yP - 8, b=7) if False else None
    seat_h(d, xv, yP)
    pts = dict(pump=(x, oy + 23), motor=(x - 13, oy + 23), tank=(x, oy), filt=(x, oy + 11.2), relief=(xr, yP - 9),
               unload=(xu, yP - 10), check=(xc, yP), acc=(xa, yP - 14), s0=(xs, yP + 8.5), v0=(xv, yP), x=x)
    return yP, pts
def accu_down(d, x, y):
    d.ax.add_patch(FancyBboxPatch((x - 3, y - 11.5), 6, 10, boxstyle="round,pad=0,rounding_size=3", fc="none", ec="k", lw=LW))
    d.line([(x - 3, y - 6.5), (x + 3, y - 6.5)], LWT)
    d.tri([(x, y - 11.5), (x - 1.2, y - 9.5), (x + 1.2, y - 9.5)])
    d.line([(x, y), (x, y - 1.5)])
def seat_h(d, x, y, b=6.5):
    """二位二通常闭电磁座阀，水平流向：两框上下叠放，接口在常态框（下框）左右。"""
    d.ax.add_patch(Rectangle((x - b / 2, y - b / 2), b, b, fc="w", ec="k", lw=LW, zorder=4))
    d.ax.add_patch(Rectangle((x - b / 2, y + b / 2), b, b, fc="w", ec="k", lw=LW, zorder=4))
    z = dict(zorder=5)
    d.ax.plot([x - b / 2, x - 0.6], [y, y], color="k", lw=LWT, **z); d.ax.plot([x - 0.6, x - 0.6], [y - 1.4, y + 1.4], color="k", lw=LWT, **z)
    d.ax.add_patch(Circle((x + 1.1, y), 0.7, fc="none", ec="k", lw=LWT, zorder=5))
    d.ax.plot([x + 2.4, x + 0.3, x + 2.4], [y - 1.2, y, y + 1.2], color="k", lw=LWT, **z)
    d.ax.plot([x + 2.4, x + b / 2], [y, y], color="k", lw=LWT, **z)
    d.ax.plot([x - b / 2 + .5, x + b / 2 - 1.8], [y + b, y + b], color="k", lw=LWT, **z)
    d.ax.add_patch(Polygon([(x + b / 2 - .6, y + b), (x + b / 2 - 2, y + b + .6), (x + b / 2 - 2, y + b - .6)], fc="k", ec="k", lw=.3, zorder=5))
    d.ax.add_patch(Rectangle((x - 1.8, y + 1.5 * b), 3.6, 3.2, fc="w", ec="k", lw=LWT, zorder=4))
    d.ax.plot([x - 1.8, x + 1.8], [y + 1.5 * b, y + 1.5 * b + 3.2], color="k", lw=LWT, zorder=5)
    d.spring(x, y - b / 2, x, y - b / 2 - 4, n=3, amp=1.0)

def chuck_circuit(d, x, yP, top, pts=None):
    """卡盘回路：10、14、11、15、13、12（夹紧：有杆腔进油、活塞杆缩回）。x 为支路 x，yP 为 P 母线。"""
    d.dot(x, yP); d.line([(x, yP), (x, yP + 6.5)])
    yr = yP + 12; reducer3(d, x + 1.2, yr)
    yo = yr + 5.5
    d.line([(x, yo), (x, yo + 8)])
    d.dot(x, yo + 4); s1 = psensor(d, x, yo + 4, side=-1)
    yv = yo + 17
    p = dir43(d, x + 2.24, yv)
    # 修正：P 口对齐支路 x
    d.line([(x, yo + 8), (p["P"][0], yo + 8), (p["P"][0], p["P"][1])])
    d.line([p["T"], (p["T"][0], p["T"][1] - 3)]); tank(d, p["T"][0], p["T"][1] - 5)
    xa, xb = p["A"][0] - 8, p["B"][0] + 8
    yj = yv + 16
    d.line([p["A"], (p["A"][0], yv + 8), (xa, yv + 8), (xa, yj - 3.5)])
    d.line([p["B"], (p["B"][0], yv + 8), (xb, yv + 8), (xb, yj - 3.5)])
    rotary_joint(d, xa, xb, yj)
    # 回转部分：13、12
    yk = yj + 13
    d.line([(xa, yj + 3.5), (xa, top - 6)])
    d.line([(xb, yj + 3.5), (xb, yk - 4.5)]); pilot_check(d, xb, yk)
    d.dash([(xa, yk), (xb - 4, yk)]); d.dot(xa, yk)
    d.tri([(xb - 4, yk), (xb - 5.4, yk + .7), (xb - 5.4, yk - .7)])
    d.line([(xb, yk + 4.5), (xb, top - 6)])
    cl, cr = cylinder(d, xa - 3, top - 6, xb - xa + 6, 9, piston_at=(xb - xa) * 0.45, rod_out=0)
    # 卡盘缸：杆向左伸出（用镜像画法）：在左端补活塞杆
    d.text(0, 0, "")
    return dict(s1=s1, r=(x + 1.2, yr), dv=(x + 2.24, yv), rj=((xa + xb) / 2, yj), pc=(xb, yk), cyl=(xa + 6, top - 1.5),
                xa=xa, xb=xb, yj=yj)

def tail_circuit(d, x, yP, top, wide=False):
    """尾座回路：16、17、18、19~25、30、26、55。x 为 R1 支路 x。"""
    d.dot(x, yP); d.line([(x, yP), (x, yP + 6.5)])
    yr = yP + 12; reducer3(d, x + 1.2, yr)
    yo = yr + 5.5
    yv = yo + 17
    p = dir43(d, x + 2.24, yv)
    d.line([(x, yo), (x, yo + 8), (p["P"][0], yo + 8), (p["P"][0], p["P"][1])])
    d.line([p["T"], (p["T"][0], p["T"][1] - 3)]); tank(d, p["T"][0], p["T"][1] - 5)
    # 阀块 55 范围
    xl, xr = x - 16, x + 34
    yb0, yb1 = yv + 11, top - 9
    d.rect(xl - 18, yb0, xr - xl + 34, yb1 - yb0, LWT, ls="--")
    # A→V1→无杆腔，B→V2→有杆腔
    y1 = yb0 + 9
    d.line([p["A"], (p["A"][0], yv + 7), (xl, yv + 7), (xl, y1 - 3.5)])
    d.line([p["B"], (p["B"][0], yv + 7), (xr, yv + 7), (xr, y1 - 3.5)])
    seat22(d, xl, y1); seat22(d, xr, y1, )
    ycl = top - 13
    yc_port = yb1 + 0
    d.line([(xl, y1 + 3.5), (xl, yc_port + 4)]); d.line([(xr, y1 + 3.5), (xr, yc_port + 4)])
    cl, cr = cylinder(d, xl - 3, yc_port + 4, xr - xl + 6, 10, piston_at=(xr - xl) * 0.42, rod_out=14)
    # V3 + 22：无杆腔 → 油箱
    yt = y1 + 10
    x3 = xl - 12
    d.dot(xl, yt); d.line([(xl, yt), (x3, yt), (x3, y1 + 3.5)]); seat22(d, x3, y1)
    d.line([(x3, y1 - 3.5), (x3, yb0 - 2)]); orifice(d, x3, yb0 - 5)
    d.line([(x3, yb0 - 8), (x3, yb0 - 11)]); tank(d, x3, yb0 - 13)
    # S2（无杆腔）、T1、S3（有杆腔）
    ys = y1 + 15
    d.dot(xl, ys); s2 = psensor(d, xl, ys, side=-1)
    d.dot(xl, ys - 0) if False else None
    yT = y1 + 20
    d.dot(xl, yT); t1 = tsensor(d, xl, yT, side=1)
    d.dot(xr, ys); s3 = psensor(d, xr, ys, side=-1)
    # R2 → V4 → 有杆腔
    x2 = xr + 14
    d.dot(x2, yP); d.line([(x2, yP), (x2, yP + 6.5)]); reducer3(d, x2 + 1.2, yr)
    d.line([(x2, yo), (x2, y1 - 3.5)]); seat22(d, x2, y1)
    d.line([(x2, y1 + 3.5), (x2, yt), (xr, yt)]); d.dot(xr, yt)
    return dict(r1=(x + 1.2, yr), r2=(x2 + 1.2, yr), dv=(x + 2.24, yv), v1=(xl, y1), v2=(xr, y1), v3=(x3, y1), v4=(x2, y1),
                orf=(x3, yb0 - 5), s2=s2, s3=s3, t1=t1, blk=(xl - 18, yb0 + 3), cyl=(xl + 8, yc_port + 14),
                xl=xl, xr=xr, yb0=yb0, yb1=yb1, x2=x2, y1=y1, rod=(xr + 10, yc_port + 9))

# ---------------- 图1 ----------------
def fig1(lab):
    d = D(165, 150, lab)
    yP, p = power_unit(d, 4, 14, P_to=158)
    c = chuck_circuit(d, 108 - 4, yP, 140) if False else None
    # 卡盘支路在左侧上方，尾座支路在右侧
    cc = chuck_circuit(d, 30, yP, 142)
    tt = tail_circuit(d, 104, yP, 142)
    d.line([(p["x"] + 80, yP), (158, yP)])
    # 标注
    L = d.lab
    L(1, p["tank"][0] + 2, p["tank"][1] + 1, p["tank"][0] + 8, p["tank"][1] - 6)
    L(2, p["filt"][0] + 1.5, p["filt"][1] + 1.5, p["filt"][0] - 8, p["filt"][1] + 3)
    L(3, p["pump"][0] + 3, p["pump"][1] - 2.8, p["pump"][0] + 7, p["pump"][1] - 9)
    L(4, p["motor"][0] - 2.8, p["motor"][1] + 2.8, p["motor"][0] - 5, p["motor"][1] + 9)
    L(5, p["relief"][0] + 4, p["relief"][1] - 3, p["relief"][0] + 7, p["relief"][1] - 13)
    L(6, p["unload"][0] + 3.5, p["unload"][1] - 2, p["unload"][0] + 8, p["unload"][1] - 13)
    L(7, p["check"][0], p["check"][1] + 1.5, p["check"][0] - 2, p["check"][1] + 9)
    L(8, p["acc"][0] + 3, p["acc"][1], p["acc"][0] + 6, p["acc"][1] - 9)
    L(9, p["s0"][0] + 2.4, p["s0"][1] + .5, p["s0"][0] + 6, p["s0"][1] + 5)
    L(29, p["v0"][0] + 3, p["v0"][1] + 8, p["v0"][0] + 8, p["v0"][1] + 13)
    L(10, cc["r"][0] + 4.5, cc["r"][1] - 2, cc["r"][0] + 12, cc["r"][1] - 4)
    L(14, cc["s1"][0] - 2.4, cc["s1"][1], cc["s1"][0] - 6, cc["s1"][1] - 6)
    L(11, cc["dv"][0] - 12, cc["dv"][1] + 4, cc["dv"][0] - 18, cc["dv"][1] + 8)
    L(15, cc["xa"] - 4, cc["yj"] + 2, cc["xa"] - 9, cc["yj"] + 6)
    L(13, cc["pc"][0] + 4, cc["pc"][1] + 2, cc["pc"][0] + 10, cc["pc"][1] + 5)
    L(12, cc["xa"] - 3, 140, cc["xa"] - 9, 146)
    L(16, tt["r1"][0] - 4.5, tt["r1"][1] - 4, tt["r1"][0] - 14, tt["r1"][1] - 7)
    L(17, tt["r2"][0] + 4.5, tt["r2"][1] + 2, tt["r2"][0] + 10, tt["r2"][1] + 8)
    L(18, tt["dv"][0] + 13, tt["dv"][1] + 1, tt["dv"][0] + 22, tt["dv"][1] + 6)
    L(19, tt["v1"][0] - 7, tt["v1"][1] - 3, tt["v1"][0] - 6, tt["v1"][1] - 10)
    L(20, tt["v2"][0] + 3.5, tt["v2"][1] - 2, tt["v2"][0] + 6, tt["v2"][1] - 10)
    L(21, tt["v3"][0] - 10.5, tt["v3"][1] + 1, tt["v3"][0] - 14, tt["v3"][1] + 5)
    L(22, tt["orf"][0] - 1, tt["orf"][1], tt["orf"][0] - 9, tt["orf"][1] - 3)
    L(23, tt["v4"][0] + 7.5, tt["v4"][1] + 1, tt["v4"][0] + 12, tt["v4"][1] + 6)
    L(24, tt["s2"][0] - 2.4, tt["s2"][1], tt["s2"][0] - 9, tt["s2"][1] + 3)
    L(25, tt["s3"][0] - 2.4, tt["s3"][1] - .5, tt["s3"][0] - 4, tt["s3"][1] - 7)
    L(30, tt["t1"][0] + 2.4, tt["t1"][1], tt["t1"][0] + 9, tt["t1"][1] + 1)
    L(26, tt["cyl"][0] + 16, tt["cyl"][1], tt["cyl"][0] + 22, tt["cyl"][1] + 4)
    L(55, tt["blk"][0], tt["blk"][1] + 10, tt["blk"][0] - 8, tt["blk"][1] + 14)
    d.title("图1")
    return d.save(1, "液压原理图")

def fig2(lab):
    d = D(120, 135, lab)
    yP = 20
    d.line([(8, yP), (110, yP)]); d.arrow(4, yP, 9, yP, LW, 2.0)
    tt = tail_circuit(d, 42, yP, 128)
    L = d.lab
    L(16, tt["r1"][0] - 4.5, tt["r1"][1] - 4, tt["r1"][0] - 14, tt["r1"][1] - 7)
    L(17, tt["r2"][0] + 4.5, tt["r2"][1] + 2, tt["r2"][0] + 10, tt["r2"][1] + 8)
    L(18, tt["dv"][0] + 13, tt["dv"][1] + 1, tt["dv"][0] + 22, tt["dv"][1] + 6)
    L(19, tt["v1"][0] - 7, tt["v1"][1] - 3, tt["v1"][0] - 6, tt["v1"][1] - 10)
    L(20, tt["v2"][0] + 3.5, tt["v2"][1] - 2, tt["v2"][0] + 6, tt["v2"][1] - 10)
    L(21, tt["v3"][0] - 10.5, tt["v3"][1] + 1, tt["v3"][0] - 14, tt["v3"][1] + 5)
    L(22, tt["orf"][0] - 1, tt["orf"][1], tt["orf"][0] - 9, tt["orf"][1] - 3)
    L(23, tt["v4"][0] + 7.5, tt["v4"][1] + 1, tt["v4"][0] + 12, tt["v4"][1] + 6)
    L(24, tt["s2"][0] - 2.4, tt["s2"][1], tt["s2"][0] - 9, tt["s2"][1] + 3)
    L(25, tt["s3"][0] - 2.4, tt["s3"][1] - .5, tt["s3"][0] - 4, tt["s3"][1] - 7)
    L(30, tt["t1"][0] + 2.4, tt["t1"][1], tt["t1"][0] + 9, tt["t1"][1] + 1)
    L(26, tt["cyl"][0] + 16, tt["cyl"][1], tt["cyl"][0] + 22, tt["cyl"][1] + 4)
    L(55, tt["blk"][0], tt["blk"][1] + 10, tt["blk"][0] - 8, tt["blk"][1] + 14)
    L(29, 8, yP, 8, yP + 8)  # 来自隔离座阀 V0 的供油
    if lab: d.text(8, yP - 4, "P", fs=8)
    d.title("图2")
    return d.save(2, "尾座双腔锁闭局部回路")

def fig3(lab):
    d = D(90, 125, lab)
    yP = 20
    d.line([(8, yP), (50, yP)]); d.arrow(4, yP, 9, yP, LW, 2.0)
    cc = chuck_circuit(d, 38, yP, 118)
    L = d.lab
    L(10, cc["r"][0] + 4.5, cc["r"][1] - 2, cc["r"][0] + 12, cc["r"][1] - 4)
    L(14, cc["s1"][0] - 2.4, cc["s1"][1], cc["s1"][0] - 6, cc["s1"][1] - 6)
    L(11, cc["dv"][0] - 12, cc["dv"][1] + 4, cc["dv"][0] - 18, cc["dv"][1] + 8)
    L(15, cc["xa"] - 4, cc["yj"] + 2, cc["xa"] - 9, cc["yj"] + 6)
    L(13, cc["pc"][0] + 4, cc["pc"][1] + 2, cc["pc"][0] + 10, cc["pc"][1] + 5)
    L(12, cc["xa"] - 3, 116, cc["xa"] - 9, 121)
    L(29, 8, yP, 8, yP + 8)
    d.title("图3")
    return d.save(3, "卡盘锁闭回路")

# ---------------- 图4 控制系统框图 ----------------
def box(d, x, y, w, h, s, fs=7.5):
    d.rect(x - w / 2, y - h / 2, w, h, LW); d.text(x, y, s, fs=fs)
def fig4(lab):
    d = D(165, 150, lab)
    cx, cy = 82.5, 82
    box(d, cx, cy, 30, 70, "控制器\n\n推力计算\nF=p1·A1-p2·A2\n\n事件触发\n判断\n\n联锁与\n诊断", 8)
    ins = [("9", "蓄能器压力\n传感器"), ("14", "卡盘压力\n传感器"), ("24", "无杆腔压力\n传感器"), ("25", "有杆腔压力\n传感器"),
           ("30", "油温传感器"), ("31", "尾座位移\n传感器"), ("32", "卡盘到位\n开关"), ("59", "门联锁开关")]
    outs = [("4", "电动机"), ("6", "电磁卸荷阀"), ("29", "隔离座阀"), ("11", "卡盘换向阀"), ("18", "尾座换向阀"),
            ("19", "第一锁闭座阀"), ("20", "第二锁闭座阀"), ("21", "微泄座阀"), ("23", "预压座阀")]
    for i, (n, s) in enumerate(ins):
        y = 140 - i * 15.5 + 0
        y = cy + 35 - 4 - i * (62 / 7)
        box(d, 25, y, 26, 7.6, s, 6.8)
        d.arrow(38, y, cx - 15, y)
        d.lab(n, 12, y + 2, 7, y + 4.5)
    for i, (n, s) in enumerate(outs):
        y = cy + 35 - 4 - i * (62 / 8)
        box(d, 140, y, 26, 6.4, s, 6.8)
        d.arrow(cx + 15, y, 127, y)
        d.lab(n, 153, y + 2, 158, y + 4.5)
    box(d, cx, 25, 40, 10, "数控系统 / 触摸屏", 8)
    d.arrow(cx - 4, cy - 35, cx - 4, 30); d.arrow(cx + 4, 30, cx + 4, cy - 35)
    d.lab(27, cx + 15, cy + 30, cx + 24, cy + 40)
    d.lab(28, cx + 20, 28, cx + 30, 32)
    d.title("图4")
    return d.save(4, "控制系统框图")

# ---------------- 图5 流程图 ----------------
def diamond(d, x, y, w, h, s, fs=7.2):
    d.ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True, fc="none", ec="k", lw=LW))
    d.text(x, y, s, fs=fs)
def term(d, x, y, s):
    d.ax.add_patch(FancyBboxPatch((x - 12, y - 3.5), 24, 7, boxstyle="round,pad=0,rounding_size=3.5", fc="none", ec="k", lw=LW))
    d.text(x, y, s, fs=7.5)
def fig5(lab):
    d = D(150, 235, lab)
    x = 62
    st = lambda k: (f"S{k} " if lab else "")
    term(d, x, 226, "开始")
    steps = [(212, st(1) + "卡盘夹紧，确认卡盘压力"), (198, st(2) + "尾座顶紧，有杆腔建立预压"),
             (184, st(3) + "双腔锁闭；泵停机或卸荷，\n关闭隔离座阀"), (170, st(4) + "采集 p1、p2、油温，\n计算 F=p1·A1-p2·A2")]
    for y, s in steps: box(d, x, y, 60, 9, s, 7.5)
    for a, b in [(222.5, 216.5), (207.5, 202.5), (193.5, 188.5), (179.5, 174.5)]: d.arrow(x, a, x, b)
    # 安全上限
    diamond(d, x, 152, 44, 14, "F > 安全上限？")
    d.arrow(x, 165.5, x, 159)
    box(d, 125, 152, 34, 10, "立即复位，\n停主轴并报警", 7.2)
    d.arrow(x + 22, 152, 108, 152)
    diamond(d, x, 130, 40, 14, "F < F_L？")
    d.arrow(x, 145, x, 137)
    box(d, 125, 130, 34, 10, st(5) + "开启补压通路，\n回复至设定压力", 7.0)
    d.arrow(x + 20, 130, 108, 130)
    diamond(d, x, 108, 40, 14, "F > F_H？")
    d.arrow(x, 123, x, 115)
    box(d, 125, 108, 34, 10, st(6) + "开启泄放通路，\n累计伸长量 ΔL", 7.0)
    d.arrow(x + 20, 108, 108, 108)
    diamond(d, x, 84, 40, 14, st(7) + "加工结束？")
    d.arrow(x, 101, x, 91)
    # S5/S6 回到 S7 判断上方
    d.line([(125, 125), (125, 113)]); d.arrow(125, 103, 125, 94) if False else None
    d.line([(125, 103), (125, 96), (x, 96)]); d.dot(x, 96, 0.5)
    # 否 → 回到 S4
    d.line([(x - 20, 84), (14, 84), (14, 170)]); d.arrow(14, 170, x - 30, 170)
    box(d, x, 64, 60, 9, st(8) + "尾座后退到位确认后，卡盘松开", 7.5)
    d.arrow(x, 77, x, 68.5)
    term(d, x, 50, "结束"); d.arrow(x, 59.5, x, 53.5)
    for (tx, ty, s) in [(x + 25, 155, "是"), (x + 2.5, 143, "否"), (x + 23, 133, "是"), (x + 2.5, 121, "否"),
                        (x + 23, 111, "是"), (x + 2.5, 99, "否"), (x - 25, 87, "否"), (x + 2.5, 74, "是")]:
        d.text(tx, ty, s, fs=7)
    d.title("图5")
    info = d.save(5, "控制方法流程图")
    return info

# ---------------- 图6 推力区间示意 ----------------
def fig6(lab):
    w, h = 150, 110
    fig = plt.figure(figsize=(w / 25.4, h / 25.4))
    ax = fig.add_axes([0.1, 0.36, 0.86, 0.58]); ax2 = fig.add_axes([0.1, 0.15, 0.86, 0.14], sharex=ax)
    F0, FL, FH, FS_ = 1.0, 0.95, 1.05, 1.25
    t = np.linspace(0, 100, 2001)
    # 示意曲线（非仿真数据）：热伸长使推力缓慢上升，油温回落/泄漏使推力缓慢下降
    F = np.empty_like(t); f = F0; ev = []
    rate = lambda tt: 0.0022 if tt < 55 else -0.0018
    for i, tt in enumerate(t):
        if i: f += rate(tt) * (t[1] - t[0])
        if f >= FH: f = F0; ev.append((tt, "H"))
        if f <= FL: f = F0; ev.append((tt, "L"))
        F[i] = f
    ax.plot(t, F, "k", lw=1.0)
    for y, ls in [(FH, (0, (5, 2))), (FL, (0, (5, 2))), (F0, (0, (1, 1.5))), (FS_, (0, (8, 2, 1, 2)))]:
        ax.axhline(y, color="k", lw=0.6, ls=ls)
    ax.set_ylim(0.85, 1.32); ax.set_xlim(0, 100)
    for a in (ax, ax2):
        for s in ("top", "right"): a.spines[s].set_visible(False)
        a.set_xticks([]); a.set_yticks([])
        a.spines["left"].set_linewidth(0.8); a.spines["bottom"].set_linewidth(0.8)
    ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False, ms=4)
    ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(), clip_on=False, ms=4)
    ax.text(-2, 1.31, "F", ha="right", fontsize=9, style="italic")
    ax2.text(101, -0.15, "t", fontsize=9, style="italic")
    # 动作脉冲
    pul = np.zeros_like(t)
    for te, k in ev: pul[(t >= te) & (t < te + 1.2)] = 1 if k == "L" else -1
    ax2.plot(t, pul, "k", lw=0.9); ax2.set_ylim(-1.4, 1.4); ax2.axhline(0, color="k", lw=0.4)
    ax2.spines["bottom"].set_visible(False)
    labels = []
    if lab:
        for y, s in [(FH, "F_H"), (F0, "F_0"), (FL, "F_L"), (FS_, "F_S")]:
            ax.text(-1.2, y, s.replace("_", "")[0] + "$_{" + s.split("_")[1] + "}$", ha="right", va="center", fontsize=8.5, style="italic")
            labels.append(s)
        te = [e for e in ev if e[1] == "H"][0][0]
        ax.annotate("泄放", (te, FH), (te + 6, 1.15), fontsize=7.5, arrowprops=dict(arrowstyle="-", lw=0.4))
        te = [e for e in ev if e[1] == "L"][0][0]
        ax.annotate("补压", (te, FL), (te + 5, 0.885), fontsize=7.5, arrowprops=dict(arrowstyle="-", lw=0.4))
        ax2.text(-1.2, 0.7, "补压", ha="right", fontsize=7); ax2.text(-1.2, -0.9, "泄放", ha="right", fontsize=7)
        ax.text(27, 1.12, "锁闭、泵停机", fontsize=7.5, ha="center")
    fig.text(0.5, 0.02, "图6", ha="center", fontsize=10.5)
    sub = "标注版" if lab else "无标注版"
    base = os.path.join(OUT, sub, "图6")
    fig.savefig(base + ".png", dpi=400, facecolor="white"); fig.savefig(base + ".svg", facecolor="white"); plt.close(fig)
    info = {"fig": 6, "title": "事件触发推力区间示意图", "size_mm": [w, h], "labeled": lab, "labels": [],
            "symbols": labels, "names": {}, "missing": [], "crossings": 0,
            "note": "示意曲线，非仿真结果；纵轴 F、横轴 t；下方为补压/泄放动作脉冲"}
    json.dump(info, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return info

if __name__ == "__main__":
    res = {}
    for lab in (True, False):
        for f in (fig1, fig2, fig3, fig4, fig5, fig6):
            i = f(lab)
            if lab: res[i["fig"]] = i
    for k, v in res.items():
        print(k, v["title"], v["labels"], "missing", v["missing"], "cross", v["crossings"])
