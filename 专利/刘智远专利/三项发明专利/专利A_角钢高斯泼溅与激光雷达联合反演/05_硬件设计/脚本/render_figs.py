# -*- coding: utf-8 -*-
"""专利A 附图渲染(黑白线条, 附图标记引线)。先运行 build_model.py 生成 ../模型/_proj.json。
运行: python render_figs.py   输出: ../预览/, ROOT/专利A_.../06_附图/{无标注版,标注版}/, 06_附图/附图标记.json
"""
import os, json, math, shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyBboxPatch, Rectangle, Ellipse
from matplotlib.path import Path
from matplotlib.patches import PathPatch

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, '..'))
PA = os.path.normpath(os.path.join(HW, '..'))
PREV = os.path.join(HW, '预览'); FIG = os.path.join(PA, '06_附图')
D_NO = os.path.join(FIG, '无标注版'); D_LB = os.path.join(FIG, '标注版')
for d in (PREV, D_NO, D_LB): os.makedirs(d, exist_ok=True)
PJ = json.load(open(os.path.join(HW, '模型', '_proj.json'), encoding='utf-8'))
LW = 0.7

NAMES = {'1': '挂架', '11': '快拆接口', '12': '减振器', '2': '主框架', '3': '激光扫描头', '4': '倾角调节机构',
         '41': '耳轴', '42': '驱动电机', '43': '蜗轮蜗杆副', '44': '角度编码器', '45': '机械限位块',
         '46': '锁止夹紧件', '5': '俯视测绘相机', '6': '仰视相机', '7': 'GNSS/INS组合导航单元',
         '8': '同步板', '9': '机载计算单元', '13': '线缆'}
MARKS = {}  # fig -> {no: name}

def save(fig, name, labeled):
    for d in ([D_LB] if labeled else [D_NO]) + [PREV]:
        fn = name + ('_标注' if labeled and d == PREV else '') + '.png'
        fig.savefig(os.path.join(d, fn), dpi=300, facecolor='white', bbox_inches='tight')
    plt.close(fig)

def draw_lines(ax, lines, lw=LW):
    for l in lines:
        a = np.array(l); ax.plot(a[:, 0], a[:, 1], 'k-', lw=lw, solid_capstyle='round')

def leaders(ax, labels, keys, extent, center=None, rpad=1.18):
    """在外圈布置数字标记并画引线(专利附图风格)"""
    xs = [p[0] for l in extent for p in l]; ys = [p[1] for l in extent for p in l]
    cx, cy = (center if center else ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2))
    rx, ry = (max(xs) - min(xs)) / 2 * rpad, (max(ys) - min(ys)) / 2 * rpad
    items = [(k, labels[k]) for k in keys if k in labels]
    items.sort(key=lambda kv: math.atan2(kv[1][1] - cy, kv[1][0] - cx))
    n = len(items); used = []
    for i, (k, (x, y)) in enumerate(items):
        a = math.atan2(y - cy, x - cx)
        # 避免过近: 与已用角度至少隔 2π/(1.6n)
        for u in used:
            if abs((a - u + math.pi) % (2 * math.pi) - math.pi) < 2 * math.pi / (1.7 * n):
                a = u + 2 * math.pi / (1.7 * n)
        used.append(a)
        tx, ty = cx + rx * math.cos(a), cy + ry * math.sin(a)
        ax.plot([x, tx], [y, ty], 'k-', lw=0.5)
        ax.plot([x], [y], 'k.', ms=2.5)
        ax.text(tx + 6 * math.cos(a), ty + 6 * math.sin(a), k, fontsize=10,
                ha='left' if math.cos(a) > 0.2 else ('right' if math.cos(a) < -0.2 else 'center'),
                va='bottom' if math.sin(a) > 0.2 else ('top' if math.sin(a) < -0.2 else 'center'))

def geo_fig(view, name, title_keys, figsize=(8, 6), section=False):
    v = PJ[view]
    for labeled in (False, True):
        fig, ax = plt.subplots(figsize=figsize); ax.set_aspect('equal'); ax.axis('off')
        if section:
            for f in v['faces']:
                verts = f['outer']; codes = [Path.MOVETO] + [Path.LINETO] * (len(verts) - 1)
                for w in f['inner']:
                    verts = verts + w; codes += [Path.MOVETO] + [Path.LINETO] * (len(w) - 1)
                ax.add_patch(PathPatch(Path(verts, codes), facecolor='white', edgecolor='k', lw=LW,
                                       hatch='////' if f['no'] in (2, 41, 43, 45, 46) else '\\\\\\\\'))
        draw_lines(ax, v['lines'])
        if labeled:
            labs = dict(v['labels'])
            if section:
                labs['4'] = labs.get('43', labs.get('41'))
            leaders(ax, labs, title_keys + (['4'] if section else []), v['lines'])
        save(fig, name, labeled)
    present = set(v['labels']) | ({'4'} if section else set())
    MARKS[name] = {k: NAMES[k] for k in title_keys + (['4'] if section else []) if k in present}

KEYS_ALL = ['1', '11', '12', '2', '3', '41', '42', '43', '44', '45', '46', '5', '6', '7', '8', '9', '13']
geo_fig('iso', '图1_载荷整体轴测图', KEYS_ALL)
geo_fig('explode', '图2_载荷爆炸图', [k for k in KEYS_ALL if k != '13'], figsize=(9, 8))
geo_fig('section', '图3_倾角调节机构剖视图', ['2', '3', '7', '41', '42', '43', '44', '45', '46'], figsize=(7, 6), section=True)

# 图4 三视图(主/俯/左)
for labeled in (False, True):
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    for ax, vw, t in zip(axs, ['front', 'top', 'side'], ['(a)主视', '(b)俯视', '(c)左视']):
        ax.set_aspect('equal'); ax.axis('off'); draw_lines(ax, PJ[vw]['lines'], 0.5)
        ax.set_title(t, fontsize=10, y=-0.12)
        if labeled: leaders(ax, PJ[vw]['labels'], ['1', '11', '12', '2', '3', '5', '6', '8', '9'], PJ[vw]['lines'])
    save(fig, '图4_载荷三视图', labeled)
MARKS['图4_载荷三视图'] = {k: NAMES[k] for k in ['1', '11', '12', '2', '3', '5', '6', '8', '9']}

# ---------- 框图工具 ----------
def blk(ax, x, y, w, h, txt, no=None, labeled=True, fs=9, dash=False):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=1.0, ls='--' if dash else '-'))
    ax.text(x + w / 2, y + h / 2, txt, ha='center', va='center', fontsize=fs, wrap=True)
    if no and labeled:
        ax.plot([x + w, x + w + 0.25], [y + h, y + h + 0.25], 'k-', lw=0.5)
        ax.text(x + w + 0.28, y + h + 0.28, str(no), fontsize=9)
def arr(ax, p, q, txt='', both=False, fs=7.5, off=(0, 0.12)):
    ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='<|-|>' if both else '-|>', lw=0.8, color='k',
                                                    shrinkA=0, shrinkB=0, mutation_scale=9))
    if txt: ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], txt, fontsize=fs, ha='center', va='bottom')

# 图5 同步电路框图
def fig5(labeled):
    fig, ax = plt.subplots(figsize=(11, 6.5)); ax.set_xlim(0, 22); ax.set_ylim(0, 13); ax.axis('off')
    blk(ax, 0.5, 9.5, 3.6, 2, 'GNSS/INS\n组合导航单元', 7, labeled)
    ax.add_patch(Rectangle((6, 3), 8, 8.8, fill=False, lw=1.2, ls='--'))
    if labeled: ax.plot([14, 14.3], [11.8, 12.2], 'k-', lw=.5); ax.text(14.35, 12.25, '8', fontsize=9)
    ax.text(6.2, 11.4, '同步板', fontsize=9)
    blk(ax, 6.6, 8.6, 3.2, 1.8, 'PPS整形与\n隔离输入', 81, labeled)
    blk(ax, 10.4, 8.6, 3.2, 1.8, '时间基准计数器\n(CPLD, 10 ns)', 82, labeled)
    blk(ax, 6.6, 5.9, 3.2, 1.8, '触发脉冲发生\n(相位可编程)', 83, labeled)
    blk(ax, 10.4, 5.9, 3.2, 1.8, '曝光中点\n时间戳锁存', 84, labeled)
    blk(ax, 8.5, 3.4, 3.2, 1.6, 'MCU 打包\n/串口与以太网', 85, labeled)
    blk(ax, 17, 9.8, 4, 1.8, '激光扫描头', 3, labeled)
    blk(ax, 17, 6.9, 4, 1.8, '俯视测绘相机', 5, labeled)
    blk(ax, 17, 4.1, 4, 1.8, '仰视相机', 6, labeled)
    blk(ax, 0.5, 3.4, 3.6, 2, '机载计算单元', 9, labeled)
    arr(ax, (4.1, 10.5), (6.6, 9.6), 'PPS')
    arr(ax, (4.1, 11.1), (17, 11.1), 'PPS + NMEA/GPRMC 授时', off=(0, 0.1))
    arr(ax, (9.8, 9.5), (10.4, 9.5))
    arr(ax, (12.0, 8.6), (12.0, 7.7))
    arr(ax, (8.2, 8.6), (8.2, 7.7))
    arr(ax, (9.8, 6.9), (17, 7.9), '触发 TRIG1', off=(1.5, 0.1))
    arr(ax, (9.8, 6.4), (17, 4.9), '触发 TRIG2', off=(1.5, -0.6))
    arr(ax, (17, 7.3), (13.6, 6.9), 'Strobe1 曝光信号', off=(0.3, -0.55))
    arr(ax, (17, 4.6), (13.6, 6.1), 'Strobe2', off=(0.6, -0.6))
    arr(ax, (12, 5.9), (11.2, 5.0)); arr(ax, (8.5, 4.2), (4.1, 4.4), '曝光中点时间戳/状态')
    arr(ax, (4.1, 3.8), (17, 3.0), '', ); ax.text(13, 2.4, '图像数据(GigE/USB3)', fontsize=7.5)
    arr(ax, (19, 9.8), (19, 9.2)); ax.plot([19, 19, 2.3], [9.2, 2.0, 2.0], 'k-', lw=.8); arr(ax, (2.3, 2.0), (2.3, 3.4))
    ax.text(10, 1.5, '点云数据(LAN TCP/IP)', fontsize=7.5)
    arr(ax, (2.3, 9.5), (2.3, 5.4), 'IMU/GNSS 原始观测', off=(-0.2, 0))
    save(fig, '图5_同步电路框图', labeled)
for l in (0, 1): fig5(l)
MARKS['图5_同步电路框图'] = {'3': '激光扫描头', '5': '俯视测绘相机', '6': '仰视相机', '7': 'GNSS/INS组合导航单元',
                         '8': '同步板', '81': 'PPS整形与隔离输入电路', '82': '时间基准计数器', '83': '触发脉冲发生电路',
                         '84': '曝光中点时间戳锁存电路', '85': '微控制器', '9': '机载计算单元'}

# 图6 系统框图
def fig6(labeled):
    fig, ax = plt.subplots(figsize=(11, 6)); ax.set_xlim(0, 22); ax.set_ylim(0, 12); ax.axis('off')
    ax.add_patch(Rectangle((0.3, 0.6), 9.4, 10.8, fill=False, lw=1.1, ls='--')); ax.text(0.5, 11, '同步采集载荷(装置)', fontsize=9)
    if labeled: ax.plot([9.7, 10], [11.4, 11.7], 'k-', lw=.5); ax.text(10.05, 11.75, '100', fontsize=9)
    blk(ax, 0.8, 8.8, 4, 1.6, '激光扫描头 + 倾角调节机构', 3, labeled, fs=8)
    blk(ax, 5.2, 8.8, 4, 1.6, '俯视/仰视全局快门相机', 5, labeled, fs=8)
    blk(ax, 0.8, 6.2, 4, 1.6, 'GNSS/INS', 7, labeled); blk(ax, 5.2, 6.2, 4, 1.6, '同步板', 8, labeled)
    blk(ax, 2.6, 3.4, 5, 1.8, '机载计算单元\n(预处理/质量评估/补测视点)', 9, labeled, fs=8)
    blk(ax, 2.6, 1.0, 5, 1.4, '挂架·快拆·减振器', 1, labeled, fs=8)
    ax.add_patch(Rectangle((11.5, 0.6), 10.2, 10.8, fill=False, lw=1.1, ls='--')); ax.text(11.7, 11, '重建系统(软件模块)', fontsize=9)
    if labeled: ax.plot([21.7, 21.9], [11.4, 11.7], 'k-', lw=.5); ax.text(21.5, 11.75, '200', fontsize=9)
    mods = [('数据预处理与时空配准模块', 201), ('初始桁架图构建模块', 202), ('角钢高斯条带生成模块', 203),
            ('影像-激光联合可微渲染模块', 204), ('桁架参数优化与拓扑更新模块', 205),
            ('规格吸附与置信度评估模块', 206), ('补测视点规划与有限元输出模块', 207)]
    for i, (t, n) in enumerate(mods):
        blk(ax, 12.5, 9.6 - i * 1.4, 7.6, 1.0, t, n, labeled, fs=8)
        if i: arr(ax, (16.3, 9.6 - (i - 1) * 1.4), (16.3, 10.6 - i * 1.4))
    for a, b in [((4.8, 9.6), (5.2, 9.6)), ((2.8, 8.8), (2.8, 7.8)), ((7.2, 8.8), (7.2, 7.8)), ((4.8, 7.0), (5.2, 7.0)),
                 ((5.0, 6.2), (5.0, 5.2))]:
        arr(ax, a, b, both=True)
    arr(ax, (7.6, 4.3), (12.5, 10.1), '同步观测数据', off=(0.2, 0.6))
    ax.plot([12.5, 10.8, 10.8], [1.3, 1.3, 3.8], 'k-', lw=.8); arr(ax, (10.8, 3.8), (7.6, 3.8), '补测视点(安全壳外)', off=(0.3, 0.1))
    save(fig, '图6_系统框图', labeled)
for l in (0, 1): fig6(l)
MARKS['图6_系统框图'] = {'100': '同步采集载荷', '1': '挂架(含快拆接口、减振器)', '3': '激光扫描头(经倾角调节机构安装)',
                       '5': '俯视/仰视相机', '7': 'GNSS/INS组合导航单元', '8': '同步板', '9': '机载计算单元',
                       '200': '重建系统', **{str(n): t for t, n in mods}} if False else None

# 图7 方法流程图
STEPS = ['S1 同步采集: PPS硬触发双相机曝光并回传曝光中点, 与激光点云、POS统一时间',
         'S2 由点云/影像构建初始桁架图: 节点坐标、杆件连接、肢宽/肢朝向/偏心、存在概率',
         'S3 确定性生成函数把每根杆件展开为角钢两肢的面元高斯条带',
         'S4 同一高斯场可微渲染影像轮廓/颜色与激光距离/回波概率',
         'S5 损失=轮廓光度项+激光距离项+无回波负证据项+图先验; 梯度仅回传至桁架参数',
         'S6 按存在概率增删杆件, 更新拓扑',
         'S7 肢宽/肢厚离散吸附至GB/T 706角钢规格表',
         'S8 拉普拉斯近似求节点协方差与杆件置信度',
         'S9 置信度达标?',
         'S10 输出含规格、偏心、置信度的梁单元有限元模型',
         'S11 置信度×有限元灵敏度规划补测视点(带电安全壳外), 返回S1']
def fig7(labeled):
    fig, ax = plt.subplots(figsize=(9, 13)); ax.set_xlim(0, 18); ax.set_ylim(0, 27); ax.axis('off')
    ys = [25 - i * 2.3 for i in range(10)]
    for i in range(10):
        t = STEPS[i]; y = ys[i]
        if i == 8:
            ax.add_patch(Polygon([[9, y + 0.9], [12.5, y], [9, y - 0.9], [5.5, y]], fill=False, lw=1))
            ax.text(9, y, t if labeled else '置信度达标?', ha='center', va='center', fontsize=9)
        else:
            ax.add_patch(Rectangle((2, y - 0.75), 14, 1.5, fill=False, lw=1))
            ax.text(9, y, t if labeled else t.split(' ', 1)[1], ha='center', va='center', fontsize=8.2, wrap=True)
        if i: arr(ax, (9, ys[i - 1] - (0.9 if i - 1 == 8 else 0.75)), (9, y + (0.9 if i == 8 else 0.75)))
    ax.text(9.3, ys[8] - 1.3, '是', fontsize=9)
    ax.add_patch(Rectangle((13.2, ys[8] - 3.0), 4.6, 2.4, fill=False, lw=1))
    ax.text(15.5, ys[8] - 1.8, (STEPS[10] if labeled else STEPS[10].split(' ', 1)[1]).replace(', ', '\n'), ha='center', va='center', fontsize=7.5)
    arr(ax, (12.5, ys[8]), (15.5, ys[8])); arr(ax, (15.5, ys[8]), (15.5, ys[8] - 0.6)); ax.text(13, ys[8] + 0.2, '否', fontsize=9)
    ax.plot([17.8, 17.9, 17.9, 16], [ys[8] - 1.8, ys[8] - 1.8, ys[0], ys[0]], 'k-', lw=.8); arr(ax, (16.6, ys[0]), (16, ys[0]))
    ax.plot([1.3, 1.3, 2], [ys[6], ys[3], ys[3]], 'k--', lw=.6); ax.text(0.3, (ys[3] + ys[6]) / 2, '迭代', fontsize=8, rotation=90)
    save(fig, '图7_方法流程图', labeled)
for l in (0, 1): fig7(l)

# 图8 高斯条带生成示意: 单根杆件 L 形截面 -> 两肢面元高斯
def fig8(labeled):
    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(121); ax.set_aspect('equal'); ax.axis('off')
    b, t = 1.0, 0.12
    L = [[0, 0], [b, 0], [b, t], [t, t], [t, b], [0, b]]
    ax.add_patch(Polygon(L, fill=False, lw=1.2))
    ax.annotate('', xy=(b, -0.15), xytext=(0, -0.15), arrowprops=dict(arrowstyle='<->', lw=.6)); ax.text(b / 2, -0.28, 'b(肢宽)', ha='center', fontsize=9)
    ax.annotate('', xy=(b + 0.12, t), xytext=(b + 0.12, 0), arrowprops=dict(arrowstyle='<->', lw=.6)); ax.text(b + 0.18, 0.02, 't', fontsize=9)
    ax.plot([0, 0.7], [0, 0.7], 'k-.', lw=.6); ax.text(0.72, 0.72, 'θ(肢朝向)', fontsize=9)
    ax.plot([-0.3, 0.0], [-0.3, 0.0], 'k:', lw=.6); ax.plot([-0.3], [-0.3], 'k+', ms=8); ax.text(-0.55, -0.42, '杆件轴线 e(偏心)', fontsize=8)
    for k in range(5):
        u = (k + 0.5) / 5 * (b - t) + t
        ax.add_patch(Ellipse((u, t / 2), (b - t) / 5, t * 0.8, fill=False, lw=.6))
        ax.add_patch(Ellipse((t / 2, u), t * 0.8, (b - t) / 5, fill=False, lw=.6))
    ax.set_xlim(-0.8, 1.5); ax.set_ylim(-0.6, 1.2); ax.set_title('(a) 角钢截面参数与两肢面元高斯', fontsize=10, y=-0.08)
    ax2 = fig.add_subplot(122, projection='3d'); ax2.set_axis_off()
    na, nb = np.array([0, 0, 0]), np.array([0.3, 0.2, 3.0])
    ax2.plot(*zip(na, nb), 'k-.', lw=.8)
    ax2.scatter(*zip(na, nb), c='k', s=15)
    d = (nb - na) / np.linalg.norm(nb - na); n1 = np.cross(d, [1, 0, 0]); n1 /= np.linalg.norm(n1); n2 = np.cross(d, n1)
    tt = np.linspace(0, 2 * np.pi, 30)
    for s in np.linspace(0.08, 0.92, 9):
        c = na + s * (nb - na)
        for leg, w in ((n1, n2), (n2, n1)):
            for j in range(3):
                cc = c + leg * (0.08 + 0.12 * j)
                pts = cc[None] + 0.05 * np.cos(tt)[:, None] * leg + 0.15 * np.sin(tt)[:, None] * d
                ax2.plot(pts[:, 0], pts[:, 1], pts[:, 2], 'k-', lw=.4)
    if labeled:
        ax2.text(*na - [0.15, 0, 0.2], '节点 i', fontsize=9); ax2.text(*nb + [0, 0, 0.1], '节点 j', fontsize=9)
        ax2.text(*(na + 0.5 * (nb - na) + n1 * 0.5), '肢1高斯', fontsize=9); ax2.text(*(na + 0.6 * (nb - na) + n2 * 0.55), '肢2高斯', fontsize=9)
    ax2.view_init(18, -60); ax2.set_box_aspect((1, 1, 2.2))
    ax2.set_title('(b) 沿杆件轴线展开的高斯条带', fontsize=10, y=-0.02)
    save(fig, '图8_角钢高斯条带生成示意图', labeled)
for l in (0, 1): fig8(l)

# 图9 视场/扫描几何(侧视, 塔身旁飞行)
def fig9(labeled):
    fig, ax = plt.subplots(figsize=(10, 7)); ax.set_aspect('equal'); ax.axis('off')
    # 塔(简化): 塔身+横担, 单位 m
    tw = [[-4, 0], [-1, 30], [1, 30], [4, 0]]; ax.plot(*zip(*tw), 'k-', lw=1)
    ax.plot([-1, -1.2, 1.2, 1], [30, 36, 36, 30], 'k-', lw=1); ax.plot([-9, 9], [30, 30], 'k-', lw=1)
    for i in range(6):
        y0, y1 = i * 5, (i + 1) * 5; x0 = 4 - 0.1 * y0; x1 = 4 - 0.1 * y1
        ax.plot([-x0, x1], [y0, y1], 'k-', lw=.4); ax.plot([x0, -x1], [y0, y1], 'k-', lw=.4)
    ax.plot([9, 9], [30, 26], 'k-', lw=.8); ax.plot([9], [26], 'ko', ms=3)
    # 安全壳: 500kV 带电体最小安全距离 5.0 m(DL/T 409 表1)
    ax.add_patch(plt.Circle((9, 26), 5.0, fill=False, ls='--', lw=.8))
    U = np.array([20, 24]); ax.add_patch(Rectangle(U - [0.8, 0.25], 1.6, 0.5, fill=False, lw=1))
    for s in (-1, 1): ax.plot([U[0] - 1.6 * s, U[0]], [U[1] + 0.3, U[1] + 0.25], 'k-', lw=1)
    # LiDAR 扫描面(侧视为线: 360°旋转镜扫描面, 倾角 α)
    a = math.radians(-10)
    for r in (16,):
        ax.plot([U[0] - r * math.cos(a), U[0] + r * math.cos(a) * 0.3], [U[1] - r * math.sin(a) * -1, U[1] + 0.3 * r * math.sin(a)], 'k-', lw=.6)
    ax.plot([U[0], U[0] - 16 * math.cos(a)], [U[1], U[1] + 16 * math.sin(a)], 'k-', lw=1.2)
    # 俯视相机: 竖直向下, 半视场 33°(f=8mm, 1.1"传感器 14.1mm 宽)
    hf = math.radians(41.4)
    for s in (-1, 1): ax.plot([U[0], U[0] + 24 * math.tan(hf) * s], [U[1], 0], 'k-', lw=.6)
    # 仰视相机: 光轴前倾25°(向塔侧, 斜向上), 半视场 49.6°(f=6mm)
    ax_ang = math.radians(180 - 65); hu = math.radians(40)
    for s in (-1, 1):
        g = ax_ang + s * hu; ax.plot([U[0], U[0] + 14 * math.cos(g)], [U[1], U[1] + 14 * math.sin(g)], 'k--', lw=.6)
    ax.set_xlim(-12, 32); ax.set_ylim(-1, 40)
    if labeled:
        for (x, y, t) in [(U[0] + 1.3, U[1] + 0.6, '100'), (U[0] - 12, U[1] + 2.8, 'P1'), (U[0] + 7, 8, 'C1'),
                          (U[0] - 5, U[1] + 12, 'C2'), (13.6, 23, 'K'), (-6, 12, 'T')]:
            ax.text(x, y, t, fontsize=10)
        ax.annotate('', xy=(14, 26), xytext=(9, 26), arrowprops=dict(arrowstyle='<->', lw=.6)); ax.text(11, 26.3, 'D', fontsize=10)
    save(fig, '图9_相机视场与激光扫描面关系示意图', labeled)
for l in (0, 1): fig9(l)
MARKS['图9_相机视场与激光扫描面关系示意图'] = {'100': '同步采集载荷', 'P1': '激光扫描面(随倾角调节机构俯仰)',
    'C1': '俯视测绘相机视场', 'C2': '仰视相机视场(覆盖塔头内侧)', 'K': '带电安全壳', 'D': '最小安全距离', 'T': '输电塔'}

# 图10 同步时序图
def fig10(labeled):
    fig, ax = plt.subplots(figsize=(11, 5)); ax.set_xlim(-1.5, 12); ax.set_ylim(-0.5, 6.5); ax.axis('off')
    rows = ['PPS', 'TRIG', 'Strobe(曝光)', '时间戳', '激光扫描线']
    for i, r in enumerate(rows):
        y = 5.5 - i * 1.25; ax.text(-1.4, y + 0.2, r, fontsize=9)
        if r == 'PPS': xs = [0, 0, 0.1, 0.1, 10, 10, 10.1, 10.1, 11.5]; ys = [0, 1, 1, 0, 0, 1, 1, 0, 0]
        elif r == 'TRIG': xs, ys = [], []; [ (xs.extend([k + .5, k + .5, k + .6, k + .6]), ys.extend([0, 1, 1, 0])) for k in (0, 2.5, 5, 7.5, 10)]
        elif r == 'Strobe(曝光)': xs, ys = [], []; [(xs.extend([k + .8, k + .8, k + 1.6, k + 1.6]), ys.extend([0, 1, 1, 0])) for k in (0, 2.5, 5, 7.5, 10)]
        elif r == '时间戳':
            xs, ys = [0, 11.5], [0, 0]
            for k in (0, 2.5, 5, 7.5, 10): ax.annotate('', xy=(k + 1.2, y + 0.8), xytext=(k + 1.2, y), arrowprops=dict(arrowstyle='->', lw=.6))
        else: xs = list(np.repeat(np.arange(0, 11.5, 0.25), 2)); ys = [0, 1, 1, 0] * (len(xs) // 4) + [0, 1][:len(xs) % 4]; ys = ys[:len(xs)]
        ax.plot([-0.3] + xs + [11.5], [y] + [y + 0.8 * v for v in ys] + [y], 'k-', lw=.8)
    if labeled:
        ax.annotate('', xy=(0.5, 6.7), xytext=(0, 6.7), arrowprops=dict(arrowstyle='<->', lw=.5)); ax.text(0.05, 6.8, 'Δφ', fontsize=8)
        ax.annotate('', xy=(1.6, 2.95), xytext=(0.8, 2.95), arrowprops=dict(arrowstyle='<->', lw=.5)); ax.text(0.9, 3.0, 'Te', fontsize=8)
        ax.text(1.3, 2.0, 't_mid = t_rise + Te/2', fontsize=8)
        ax.text(4.6, 6.15, 'T_PPS = 1 s;  触发周期 = T_PPS / N', fontsize=8)
    save(fig, '图10_同步时序图', labeled)
for l in (0, 1): fig10(l)

MARKS['图6_系统框图'] = {'100': '同步采集载荷', '1': '挂架(含快拆接口、减振器)', '3': '激光扫描头(经倾角调节机构安装)',
                       '5': '俯视/仰视相机', '7': 'GNSS/INS组合导航单元', '8': '同步板', '9': '机载计算单元',
                       '200': '重建系统', **{str(n): t for t, n in mods}} if (mods := [('数据预处理与时空配准模块', 201), ('初始桁架图构建模块', 202), ('角钢高斯条带生成模块', 203), ('影像-激光联合可微渲染模块', 204), ('桁架参数优化与拓扑更新模块', 205), ('规格吸附与置信度评估模块', 206), ('补测视点规划与有限元输出模块', 207)]) else None
MARKS['图7_方法流程图'] = {s.split(' ')[0]: s.split(' ', 1)[1] for s in STEPS}
MARKS['图8_角钢高斯条带生成示意图'] = {'b': '肢宽', 't': '肢厚', 'θ': '肢朝向角', 'e': '偏心', '节点i/j': '桁架节点'}
MARKS['图10_同步时序图'] = {'Δφ': '触发相对PPS相位', 'Te': '曝光时长', 't_mid': '曝光中点时间戳'}
out = dict(说明='附图标记表; 装置标记与权利要求一致(1挂架,11快拆,12减振器,2主框架,3激光头,4倾角机构,41耳轴,42电机,43蜗轮蜗杆,44编码器,45限位块,5俯视相机,6仰视相机,7GNSS/INS,8同步板,9计算单元); 46锁止夹紧件、13线缆、81–85同步板子电路、100/200、201–207为补充标记',
           全局=NAMES, 各图=MARKS)
json.dump(out, open(os.path.join(FIG, '附图标记.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
shutil.copy(os.path.join(FIG, '附图标记.json'), os.path.join(PREV, '附图标记.json'))
print('done')
