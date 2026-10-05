# -*- coding: utf-8 -*-
"""P4 新增附图（图4～图6）：二维示意图，几何取自 P1 出图模型（tc_build_model.py）坐标。
输出 05_附图/标注版|无标注版/图N.png（400 dpi）、.svg、.json（标注版含 labels）。纯黑白，图中只有附图标记。
用法：.venv\\Scripts\\python.exe 07_脚本\\p4_figs.py"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle
from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
OUT = {k: os.path.join(PKG, "05_附图", k) for k in ("标注版", "无标注版")}
plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["svg.fonttype"] = "none"
LW = 0.9


class Fig:
    def __init__(self, n, title, xlim, ylim, width_mm=154.0):
        self.n, self.title, self.xlim, self.ylim = n, title, xlim, ylim
        self.items, self.labels = [], []
        w = xlim[1] - xlim[0]
        h = ylim[1] - ylim[0]
        self.margin = 0.22 * w
        tot_w = w + 2 * self.margin
        self.wmm = width_mm
        self.hmm = width_mm * h / tot_w + 6
        self.fig = plt.figure(figsize=(self.wmm / 25.4, self.hmm / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(xlim[0] - self.margin, xlim[1] + self.margin)
        pad = (self.hmm / self.wmm * tot_w - h) / 2
        self.ax.set_ylim(ylim[0] - pad, ylim[1] + pad)
        self.ax.set_aspect("equal")
        self.ax.axis("off")

    def poly(self, pts, hatch=None, ls="-", lw=LW, fill="white", z=1):
        self.ax.add_patch(Polygon(pts, closed=True, facecolor=fill, edgecolor="black", lw=lw, ls=ls, hatch=hatch, zorder=z))

    def rect(self, x0, x1, y0, y1, **kw):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)

    def line(self, pts, ls="-", lw=LW, z=3):
        a = np.array(pts)
        self.ax.plot(a[:, 0], a[:, 1], color="black", lw=lw, ls=ls, zorder=z, solid_capstyle="butt")

    def circle(self, c, r, hatch=None, fill="white", ls="-", z=2):
        self.ax.add_patch(Circle(c, r, facecolor=fill, edgecolor="black", lw=LW, hatch=hatch, ls=ls, zorder=z))

    def label(self, num, anchor, side):
        self.labels.append((num, anchor, side))

    def _draw_labels(self):
        fs = 10
        x0, x1 = self.xlim
        for side in ("L", "R"):
            items = sorted([l for l in self.labels if l[2] == side], key=lambda l: -l[1][1])
            if not items:
                continue
            ys = [l[1][1] for l in items]
            gap = (self.ylim[1] - self.ylim[0]) / max(len(items) + 1, 9)
            for i in range(1, len(ys)):
                ys[i] = min(ys[i], ys[i - 1] - gap)
            lo = self.ylim[0]
            if ys[-1] < lo:
                shift = lo - ys[-1]
                ys = [y + shift for y in ys]
                for i in range(len(ys) - 2, -1, -1):
                    ys[i] = max(ys[i], ys[i + 1] + gap)
            tx = x0 - self.margin * 0.55 if side == "L" else x1 + self.margin * 0.55
            ex = x0 - self.margin * 0.12 if side == "L" else x1 + self.margin * 0.12
            for (num, (ax_, ay_), _), y in zip(items, ys):
                self.ax.plot([ax_, ex, tx + (8 if side == "L" else -8)], [ay_, y, y], color="black", lw=0.6, zorder=9)
                self.ax.plot([ax_], [ay_], "o", color="black", ms=1.8, zorder=10)
                self.ax.text(tx, y, num, ha="right" if side == "L" else "left", va="center", fontsize=fs, zorder=10)

    def save(self):
        res = {}
        for ver in ("无标注版", "标注版"):
            if ver == "标注版":
                self._draw_labels()
            base = os.path.join(OUT[ver], f"图{self.n}")
            self.fig.savefig(base + ".png", dpi=400, facecolor="white")
            self.fig.savefig(base + ".svg", facecolor="white")
            im = Image.open(base + ".png").convert("L").point(lambda v: 0 if v < 160 else 255).convert("1")
            im.save(base + ".png", dpi=(400, 400))
            j = {"fig": self.n, "title": self.title, "size_mm": [round(self.wmm, 1), round(self.hmm, 1)],
                 "labels": sorted({l[0] for l in self.labels}, key=lambda s: int(s)) if ver == "标注版" else [],
                 "source": "07_脚本/p4_figs.py（二维示意，几何取自 P1 出图模型坐标）"}
            if ver == "标注版":
                json.dump(j, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            res[ver] = base
        plt.close(self.fig)
        return res


def hatch_lw():
    plt.rcParams["hatch.linewidth"] = 0.5


hatch_lw()

# ====================================================================== 图4 微位移加载单元俯视示意
f = Fig(4, "微位移加载单元的俯视示意图", (585, 1075), (395, 800))
f.rect(585, 1075, 395, 625, lw=LW)                                   # 模拟床身 43（局部）
f.line([(585, 395), (585, 625)], lw=0.4)
f.rect(600, 750, 430, 665, ls="--")                                  # 加载座底板（被遮挡部分虚线）
f.rect(600, 640, 440, 560, hatch="////")                             # 加载座挡壁（剖面）
f.rect(635, 700, 640, 665)                                           # 丝杠支承板
f.poly([(640, 430), (640, 630), (690, 630), (670, 430)])             # 楔块 63
f.poly([(671, 440), (689, 620), (740, 620), (740, 440)])             # 从动楔座 64
f.rect(742, 768, 472, 528)                                           # 推力传感器 49
f.rect(740, 742, 488, 512)
f.rect(768, 770, 488, 512)
for y0, y1 in ((455, 475), (525, 545)):                              # 直线导轨 50
    f.rect(760, 970, y0, y1, ls="--")
    f.rect(900, 970, y0, y1)
f.rect(770, 900, 440, 560)                                           # 工件模拟滑块 51
f.rect(860, 900, 410, 440)                                           # 凸耳
f.line([(878, 522), (900, 522)], ls="--")
f.line([(878, 478), (900, 478)], ls="--")
f.poly([(880, 500), (920, 480), (920, 520)], z=4)                    # 顶尖 52
f.rect(920, 1060, 480, 520, z=4)
f.rect(900, 922, 422, 428)                                           # 位移传感器测杆
f.rect(922, 1035, 415, 435)                                          # 位移传感器 56
f.rect(1035, 1055, 400, 450)                                         # 传感器支架 81
f.rect(659, 675, 470, 640, ls="--", z=5)                             # 滚珠丝杠 62（楔块内部分虚线）
f.rect(659, 675, 640, 660, z=5)
f.rect(651, 683, 660, 680)                                           # 联轴器 65
f.rect(627, 707, 680, 695)                                           # 电机法兰
f.rect(632, 702, 695, 770)                                           # 伺服电机 47
f.rect(650, 685, 770, 782)
f.label("43", (595, 410), "L")
f.label("48", (620, 470), "L")
f.label("63", (655, 560), "L")
f.label("62", (667, 650), "L")
f.label("65", (660, 670), "L")
f.label("47", (660, 740), "L")
f.label("64", (715, 600), "R")
f.label("49", (755, 520), "R")
f.label("51", (830, 545), "R")
f.label("50", (950, 540), "R")
f.label("52", (990, 510), "R")
f.label("56", (980, 430), "R")
f.label("81", (1045, 445), "R")
f.save()

# ====================================================================== 图5 卡盘模拟单元纵剖示意
f = Fig(5, "卡盘模拟单元的纵剖示意图", (60, 640), (880, 1300))
f.rect(110, 640, 880, 930)                                           # 模拟床身 43（局部）
f.rect(160, 280, 930, 1015)                                          # 卡盘缸支座 84
f.rect(140, 300, 1015, 1145, hatch="////")                           # 卡盘液压缸 12 缸体（剖面）
f.rect(150, 290, 1025, 1135)                                         # 缸腔
f.rect(205, 225, 1027, 1133, hatch="xxxx")                           # 活塞
f.rect(225, 600, 1068, 1092)                                         # 拉杆 83
for i in range(4):                                                   # 碟簧组 82（对合碟簧截面）
    x = 302 + 6 * i
    f.line([(x, 1100), (x + 6, 1120)], lw=1.1)
    f.line([(x, 1060), (x + 6, 1040)], lw=1.1)
    f.line([(x + 6, 1120), (x + 6, 1120)], lw=1.1)
f.rect(326, 340, 1035, 1062, hatch="////")                           # 夹紧力传感器 44（环形，剖面）
f.rect(326, 340, 1098, 1125, hatch="////")
f.rect(340, 520, 930, 1180)                                          # 主轴箱模拟座 45
f.rect(340, 520, 1064, 1096, fill="white", z=2)                      # 通孔
f.rect(340, 520, 1068, 1092, z=3)
f.rect(520, 580, 980, 1180)                                          # 模拟卡盘 46
f.rect(580, 605, 1060, 1100)                                         # 拉杆螺母
f.rect(375, 425, 1180, 1205)                                         # 泄漏模拟针阀 15
f.rect(394, 406, 1205, 1225)
f.line([(285, 1145), (285, 1250), (60, 1250)], lw=1.4)               # 供油管路 87（接夹紧腔）
f.line([(285, 1250), (400, 1250), (400, 1225)], lw=1.4)
f.line([(425, 1192), (470, 1192), (470, 1280), (60, 1280)], lw=1.4)  # 回油管路 86
f.label("43", (200, 905), "L")
f.label("84", (190, 970), "L")
f.label("12", (160, 1140), "L")
f.label("87", (120, 1250), "L")
f.label("86", (120, 1280), "L")
f.label("15", (400, 1195), "R")
f.label("82", (314, 1110), "R")
f.label("44", (333, 1120), "R")
f.label("45", (450, 1000), "R")
f.label("83", (560, 1080), "R")
f.label("46", (550, 1160), "R")
f.save()

# ====================================================================== 图6 尾座液压缸与温控夹套横剖示意
f = Fig(6, "尾座液压缸与温控夹套的横剖示意图", (230, 620), (870, 1210))
f.rect(380, 620, 870, 930)                                           # 模拟床身 43（局部）
f.rect(465, 535, 930, 1015)                                          # 尾座缸支座 88
f.rect(437, 563, 1015, 1125, hatch="////")                           # 温控夹套 61（剖面，U 形）
f.rect(449, 551, 1027, 1126, fill="white", z=2)
for (cy, cz) in ((443, 1045), (443, 1075), (443, 1105), (557, 1045), (557, 1075), (557, 1105), (470, 1021), (500, 1021), (530, 1021)):
    f.circle((cy, cz), 3.2, z=4)                                     # 夹套内流道
f.rect(455, 545, 1035, 1125, hatch="\\\\\\\\", z=3)                 # 缸筒 66（剖面）
f.circle((500, 1080), 31.5, z=4)                                     # 缸腔
f.circle((500, 1080), 17.5, hatch="xxxx", z=5)                       # 活塞杆
f.rect(455, 545, 1125, 1195)                                         # 锁闭阀块 55
f.rect(470, 485, 1195, 1210)
f.rect(515, 530, 1195, 1210)
f.rect(420, 437, 1043, 1053, z=4)                                    # 温控介质接口 74
f.rect(420, 437, 1097, 1107, z=4)
f.line([(420, 1048), (330, 1048), (330, 985)], lw=1.4)               # 温控介质软管 89
f.line([(420, 1102), (305, 1102), (305, 985)], lw=1.4)
f.rect(240, 360, 880, 985)                                           # 循环恒温槽 85
f.rect(255, 290, 950, 970)
f.label("85", (300, 930), "L")
f.label("89", (330, 1030), "L")
f.label("74", (428, 1102), "L")
f.label("61", (443, 1090), "L")
f.label("55", (500, 1170), "R")
f.label("66", (540, 1110), "R")
f.label("88", (520, 960), "R")
f.label("43", (600, 900), "R")
f.save()
print("图4～图6 已生成")
