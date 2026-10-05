# -*- coding: utf-8 -*-
"""R3 数值与术语一致性审计（只读）。
用法：python audit_numbers.py [--round N]
读：07_脚本/patent_text.js、patent_desc.js（经 node 导出）或 06_申请文件/_expanded.json；08_技术交底书/*.md；
    真值源 00_设计基准、02_详细设计/数据、03_仿真验证/数据、05_附图/numerals*.json、附图清单、标注版/图N.json。
写：10_审查与迭代/数值一致性审计_第N轮.md
"""
import json, math, re, subprocess, sys, glob, os, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / '07_脚本'
issues = []   # (类别, 位置, 文中值, 真值源及值, 建议)
notes = []


def add(cat, loc, txt, truth, sug):
    issues.append((cat, loc, txt, truth, sug))


def loadj(p):
    t = Path(p).read_text(encoding='utf-8')
    t = re.sub(r'\bNaN\b|-?Infinity', 'null', t)
    return json.loads(t)

# ------------------------------------------------------------------ 真值源
B = loadj(ROOT / '00_设计基准/设计基准参数.json')
TRUTH = []  # (value, source)


def flat(o, src, pre=''):
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        if math.isfinite(o):
            TRUTH.append((float(o), f'{src}:{pre}'))
    elif isinstance(o, dict):
        for k, v in o.items():
            flat(v, src, f'{pre}.{k}' if pre else str(k))
            for m in re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)', str(k)):   # 键名中的数（如 F0=2000）
                TRUTH.append((float(m.group(1)), f'{src}:{pre}.{k}[键]'))
    elif isinstance(o, list):
        if len(o) > 60:   # 时程序列只取极值
            nums = [x for x in o if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)]
            if nums:
                TRUTH.append((max(nums), f'{src}:{pre}[max]')); TRUTH.append((min(nums), f'{src}:{pre}[min]'))
            return
        for i, v in enumerate(o):
            flat(v, src, f'{pre}[{i}]')
    elif isinstance(o, str):
        for m in re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)', o):
            TRUTH.append((float(m.group(1)), f'{src}:{pre}[文]'))

SRC_FILES = [ROOT / '00_设计基准/设计基准参数.json'] + sorted((ROOT / '02_详细设计/数据').glob('*.json')) + \
    sorted((ROOT / '03_仿真验证/数据').glob('*.json'))
for f in SRC_FILES:
    try:
        flat(loadj(f), f.relative_to(ROOT).as_posix())
    except Exception as e:
        notes.append(f'真值源读取失败 {f.name}: {e}')
# BOM.csv 文本数字
bom = ROOT / '02_详细设计/BOM.csv'
if bom.exists():
    for m in re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)', bom.read_text(encoding='utf-8-sig', errors='ignore')):
        TRUTH.append((float(m.group(1)), '02_详细设计/BOM.csv'))
TV = sorted(TRUTH)

# ------------------------------------------------------------------ 算例复算（同 calc.js 公式，独立实现）
TC = B['尾座液压缸26']
D, d, Sx = TC['缸径'], TC['杆径'], TC['行程']
A1 = math.pi / 4 * D * D; A2 = math.pi / 4 * (D * D - d * d)
beta = B['油液']['有效体积模量_锁闭腔_MPa']; betaH = B['油液']['有效体积模量_含软管_MPa']
alpha = B['油液']['体膨胀系数_1_K']; km = B['尾座机械刚度']['k_m_N_um']
Vb = B['锁闭容积']['阀块直装缸体_每腔死容积'] * 1e3; Vh = B['锁闭容积']['常规软管连接_每腔附加容积'] * 1e3
F0 = B['尾座推力']['F0_额定']; ppre = B['预压']['有杆腔预压压力_p_pre']


def lock(x, hose=False):
    Vd = Vb + Vh if hose else Vb; b = betaH if hose else beta
    V1 = A1 * x + Vd; V2 = A2 * (Sx - x) + Vd
    k1 = b * A1 ** 2 / V1 / 1e3; k2 = b * A2 ** 2 / V2 / 1e3
    return dict(V1=V1 / 1e3, V2=V2 / 1e3, k1=k1, k2=k2, Ks=k1 * km / (k1 + km), Kd=(k1 + k2) * km / (k1 + k2 + km),
                Ts=b * alpha * A1 * km / (k1 + km), Td=b * alpha * (A1 - A2) * km / (k1 + k2 + km))

p1set = lambda F, pp=ppre: (F + pp * A2) / A1
DER = {}
L70 = lock(70); L70h = lock(70, True)
for k, v in L70.items(): DER[f'x70.{k}'] = v
for k, v in L70h.items(): DER[f'x70软管.{k}'] = v
for x in (20, 130):
    for k, v in lock(x).items(): DER[f'x{x}.{k}'] = v
for F in (2000, 4000, 6000, 8000, 10000, 12000): DER[f'p1set(F0={F})'] = p1set(F)
DER['A1'] = A1; DER['A2'] = A2; DER['A1-A2'] = A1 - A2
DER['FL'] = 0.95 * F0; DER['FH'] = 1.05 * F0; DER['Fsafe'] = 1.25 * F0
DER['漂移单/F0%'] = L70['Ts'] / F0 * 100
DER['伸长57.5推力单'] = 57.5 * L70['Ks']; DER['伸长57.5推力双'] = 57.5 * L70['Kd']
DER['伸长138推力双'] = 138 * L70['Kd']; DER['伸长138推力单'] = 138 * L70['Ks']
DER['刚度提高%'] = (L70['Kd'] / L70['Ks'] - 1) * 100; DER['漂移降低%'] = (1 - L70['Td'] / L70['Ts']) * 100
DER['漂移比'] = L70['Ts'] / L70['Td']
DER['半带宽N'] = 0.05 * F0; DER['半带宽MPa'] = 0.05 * F0 / A1
DER['F12000压差'] = p1set(12000) - ppre
DER['可行F0上限'] = (B['蓄能器8']['最低工作压力_pmin'] - 0.5) * A1 - ppre * A2
DER['算例ΔFT(0.1K)'] = 0.1 * L70['Td']
DER['算例ΔL'] = (300 - round(0.1 * L70['Td'], 1)) / round(L70['Kd'], 1)
for k, v in DER.items(): TV.append((v, f'复算:{k}'))
TV.sort()

# 基准推导值与复算对照
for key, dk, nd in [('x=70mm时V1_cm3', 'V1', 1), ('V2_cm3', 'V2', 1), ('k1_油柱_N_um', 'k1', 1), ('k2_油柱_N_um', 'k2', 1),
                    ('K_单腔锁闭_串联_N_um', 'Ks', 1), ('K_双腔预压锁闭_串联_N_um', 'Kd', 1),
                    ('油温热漂移推力_单腔锁闭_N_K', 'Ts', 0), ('油温热漂移推力_双腔锁闭_N_K', 'Td', 0)]:
    bv = B['额定工况推导值'][key]
    if abs(round(L70[dk], nd) - bv) > 0.51 * 10 ** -nd:
        add('算例', '设计基准.额定工况推导值', f'{key}={bv}', f'复算 {L70[dk]:.4g}', '更正基准或核对公式')
for F, key in [(6000, '无杆腔设定压力_p1_set_额定'), (2000, 'p1_set_F0=2000'), (12000, 'p1_set_F0=12000')]:
    if abs(p1set(F) - B['预压'][key]) > 6e-4:
        add('算例', '设计基准.预压', f'{key}={B["预压"][key]}', f'复算 {p1set(F):.4f}', '更正')

# ------------------------------------------------------------------ 申请文本读取
ROLES = {}
FIGS = []
DUMP = r"""
const path=require('path');const S=process.argv[1];
const out={};const err={};
try{const r=require(path.join(S,'roles.js'));out.ROLE=r.ROLE;out.FIGS=r.FIGS;}catch(e){err.roles=String(e).slice(0,300)}
try{const t=require(path.join(S,'patent_text.js'));out.title=t.title;out.abstract=t.abstract;out.claims=t.claims;}catch(e){err.text=String(e).slice(0,300)}
try{const d=require(path.join(S,'patent_desc.js'));out.description=d.description;}catch(e){err.desc=String(e).slice(0,300)}
out.err=err;process.stdout.write(JSON.stringify(out));
"""
src = {}
try:
    r = subprocess.run(['node', '-e', DUMP, str(S)], capture_output=True, timeout=300, cwd=str(S))
    src = json.loads(r.stdout.decode('utf-8') or '{}')
except Exception as e:
    notes.append(f'node 导出失败: {e}')
ROLES = src.get('ROLE', {}); FIGS = src.get('FIGS', [])
for k, v in (src.get('err') or {}).items():
    add('源文件', f'07_脚本/{ {"roles":"roles.js","text":"patent_text.js","desc":"patent_desc.js"}[k] }', 'require 失败', v.replace('\n', ' ')[:200],
        '源文件当前不可解析（可能仍在编辑），修复后复审')

# 附图标记表
NUMA = loadj(ROOT / '05_附图/numerals.json'); NUMB = loadj(ROOT / '05_附图/numerals_structure.json')
clean = lambda s: re.sub(r'[A-Z]\d$', '', re.sub(r'（[^）]*）', '', s).split('/')[0]).strip()
NAME = {}
for tab in (NUMA, NUMB):
    for k, v in tab.items():
        if re.fullmatch(r'\d+', k) and k not in NAME:
            NAME[k] = clean(v['name'] if isinstance(v, dict) else v)


def render(s):
    s = re.sub(r'\{(\d+)\}', lambda m: NAME.get(m.group(1), '?') + m.group(1), s)
    s = re.sub(r'\{~(\d+)\}', lambda m: NAME.get(m.group(1), '?'), s)
    s = re.sub(r'\{#(\d+)\}', lambda m: m.group(1), s)
    s = re.sub(r'[_^]\{([^}]*)\}', r'\1', s).replace('*', '')
    return s


def paras_of(x):
    if isinstance(x, str): return [x]
    if isinstance(x, dict):
        out = []
        for k in ('text', 'caption'):
            if k in x: out.append(str(x[k]))
        for row in [x.get('head', [])] + x.get('rows', []):
            out.append(' | '.join(map(str, row)))
        return out
    return []

DOCS = {}   # 名称 -> [(位置, 原始记号文本, 渲染文本)]
exp = ROOT / '06_申请文件/_expanded.json'
if src.get('abstract'):
    DOCS['摘要'] = [('摘要', src['abstract'], render(src['abstract']))]
if src.get('claims'):
    DOCS['权利要求'] = [(f'权{i + 1}', p, render(p)) for i, c in enumerate(src['claims']) for p in c['paras']]
if src.get('description'):
    lst = []
    for i, x in enumerate(src['description']):
        for p in paras_of(x): lst.append((f'说明书段{i + 1}', p, render(p)))
    DOCS['说明书'] = lst
if exp.exists():
    notes.append(f'_expanded.json 存在（{datetime.datetime.fromtimestamp(exp.stat().st_mtime):%H:%M}），用于附图标记核对')
for md in sorted((ROOT / '08_技术交底书').glob('*.md')):
    DOCS['交底书'] = [(f'交底书L{i + 1}', l, l) for i, l in enumerate(md.read_text(encoding='utf-8').splitlines())]
for md, tag in [(ROOT / '02_详细设计/详细设计说明书.md', '详细设计'), (ROOT / '03_仿真验证/仿真验证报告.md', '仿真报告')]:
    if md.exists():
        DOCS[tag] = [(f'{tag}L{i + 1}', l, l) for i, l in enumerate(md.read_text(encoding='utf-8').splitlines())]

# ------------------------------------------------------------------ 数值抽取与比对
UNIT = r'(MPa|bar|kN|N/µm|N/μm|N/um|N/K|N|mm|µm|μm|um|cm\^?\{?3\}?|cm³|mL/min|L/min|L|K/min|K|ms|s|min|kWh|Wh|kW|kJ|W|%|r/min|rpm|Hz|℃|°C|元|h|dpi)'
NUMRE = re.compile(r'(?<![\w.#{])([+\-−]?\d+(?:\.\d+)?)\s*(?:～|~|-)?\s*' + UNIT + r'(?![A-Za-z])')
CONV = {'kN': [1000, 1], 'kWh': [1, 1000, 3600], 'Wh': [1, 1 / 1000, 3.6], 'kW': [1, 1000], 'W': [1, 1 / 1000],
        'L': [1, 1000], 'mL/min': [1], 'bar': [0.1, 1], '%': [1, 0.01], 'µm': [1], 'μm': [1], 'um': [1], 'min': [1, 60], 's': [1, 1 / 60, 1000]}


def matched(val, txt_num, unit):
    nd = len(txt_num.split('.')[1]) if '.' in txt_num else 0
    for c in CONV.get(unit, [1]):
        v = val * c
        tol = 0.5 * 10 ** -nd * abs(c) * 1.0001
        if nd == 0 and abs(v) >= 100:
            tol = max(tol, abs(v) * 0.006)   # 取整到有效数字
        if nd == 0 and abs(v) >= 1000:
            tol = max(tol, abs(v) * 0.0)
        lo, hi = v - tol, v + tol
        # 二分查找
        import bisect
        i = bisect.bisect_left(TV, (lo, ''))
        while i < len(TV) and TV[i][0] <= hi:
            return TV[i]
    return None


def scan(docname):
    res = []
    for loc, raw, txt in DOCS.get(docname, []):
        t = re.sub(r'图\s*\d+|权利要求\s*\d+|S\d+|[VRSTMF]\d|表\s*\d+|式[（(]\d+[)）]|实施例\s*\d+|第\s*\d+', ' ', txt)
        t = t.replace('−', '-')
        for m in NUMRE.finditer(t):
            num, unit = m.group(1).lstrip('+'), m.group(2)
            try: v = abs(float(num))
            except ValueError: continue
            if v == 0: continue
            hit = matched(v, num.lstrip('-'), unit)
            ctx = t[max(0, m.start() - 18): m.end() + 6].replace('\n', ' ')
            res.append((loc, num, unit, hit, ctx))
    return res

SCAN = {k: scan(k) for k in DOCS if k not in ('详细设计', '仿真报告')}
for k, rows in SCAN.items():
    for loc, num, unit, hit, ctx in rows:
        if hit is None:
            add('数值无真值源', loc, f'{num} {unit}（…{ctx}…）', '未在基准/详设/仿真数据/复算中找到（含单位换算、有效数字容差）',
                '核对来源；若为新数据须先写入真值源')

# ------------------------------------------------------------------ 关键参数跨文档一致性（定向）
KEY = [  # (名称, 正则, 期望, 小数位容差, 真值源)
    ('p1_set额定', r'2\.9\d+\s*MPa', 2.962, 0.0005, 'p1set(6000)'),
    ('K单腔', r'单腔[^。；]{0,30}?(\d+\.\d)\s*N/[µμu]m', 33.3, 0.05, '基准 K_单腔'),
    ('K双腔', r'(?:双腔|提高到|提高至)[^。；]{0,30}?(\d+\.\d)\s*N/[µμu]m', None, None, ''),
    ('热漂移单', r'(17\d\d)\s*N/K', 1746, 0.5, '基准'),
    ('热漂移双', r'(4[34]\d)\s*N/K', 440, 0.5, '基准'),
]
for doc in ('摘要', '权利要求', '说明书', '交底书'):
    for loc, raw, txt in DOCS.get(doc, []):
        for m in re.finditer(r'(\d+\.\d+)\s*MPa', txt):
            pass
        for m in re.finditer(r'(1[67]\d\d)\s*N/K', txt):
            if abs(float(m.group(1)) - round(L70['Ts'])) > 0.5 and abs(float(m.group(1)) - round(L70h['Ts'])) > 0.5:
                add('跨文档', loc, m.group(0), f'单腔热漂移 复算 {L70["Ts"]:.0f}（软管 {L70h["Ts"]:.0f}）', '统一')
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*%', txt):
            pass

# 能耗口径：交底书/说明书 kWh 与 energy.json
EN = loadj(ROOT / '03_仿真验证/数据/energy.json')
C3 = loadj(ROOT / '02_详细设计/数据/c03_蓄能器与能耗.json')
try:
    e = {k: v['单件电能kWh'] for k, v in EN['单件循环'].items()}
    sav = (1 - e['M2'] / e['M0']) * 100
    DER['仿真节能率M2%'] = sav
    sav_d = C3['循环能耗']['方案']['M3']['相对M0节能率'] * 100
    if abs(sav - sav_d) > 1:
        add('跨文档口径', '03_仿真验证/energy.json vs 02_详细设计/c03', f'仿真 M2 节能率 {sav:.1f}%（单件 {e["M2"]:.4f} kWh，M0 {e["M0"]:.3f} kWh）',
            f'详设 M3（同为本发明方案）节能率 {sav_d:.1f}%（单件 {C3["循环能耗"]["方案"]["M3"]["单件能耗_Wh"]} Wh，M0 {C3["循环能耗"]["方案"]["M0"]["单件能耗_Wh"]} Wh）',
            '申请文本只引一个口径并注明来源；另注意方案代号：详设 M3 = 仿真 M2 = 本发明')
except Exception as ex:
    notes.append(f'能耗口径检查跳过: {ex}')

# 详设 vs 仿真 蓄能器可用容积 与基准
acc = B['蓄能器8']
c3a = C3['蓄能器']
if abs(acc['可用容积_绝热_cm3'] - c3a['可用容积_绝热n1.4_cm3']) > 1:
    add('跨文档', '设计基准.蓄能器8.可用容积_绝热', f'{acc["可用容积_绝热_cm3"]} cm3', f'c03 复算 {c3a["可用容积_绝热n1.4_cm3"]} cm3', '文本引用时用 111.5（约 112）或注明基准近似')
if abs(acc['可用容积_等温_cm3'] - c3a['可用容积_等温_cm3']) > 1:
    add('跨文档', '设计基准.蓄能器8.可用容积_等温', f'{acc["可用容积_等温_cm3"]} cm3', f'c03 复算 {c3a["可用容积_等温_cm3"]} cm3', '同上')

# 静刚度：解析 45.5 vs 仿真 42.6，文本须区分
ST = loadj(ROOT / '03_仿真验证/数据/stiff.json')
try:
    i70 = [round(x) for x in ST['伸出量mm']].index(70)
    simK = ST['静刚度N_um']['M2'][i70]
    if abs(simK - L70['Kd']) / L70['Kd'] > 0.03:
        notes.append(f'口径提示：x=70 双腔静刚度 解析 {L70["Kd"]:.1f} N/µm（基准）与仿真 {simK:.1f} N/µm 不同（仿真含其他柔度），文本引用时须注明“解析”或“仿真”。')
        for doc in ('摘要', '权利要求', '说明书', '交底书'):
            for loc, raw, txt in DOCS.get(doc, []):
                for m in re.finditer(r'(4[2-6]\.\d)\s*N/[µμu]m', txt):
                    if not re.search(r'解析|仿真|表\s*\d', txt):
                        add('口径未注明', loc, m.group(0), f'解析 {L70["Kd"]:.1f} / 仿真 {simK:.1f}', '注明是解析值还是仿真值')
except Exception as ex:
    notes.append(f'刚度口径检查跳过: {ex}')

# ------------------------------------------------------------------ 附图标记
names_A = {k: (v['name'] if isinstance(v, dict) else v) for k, v in NUMA.items() if re.fullmatch(r'\d+', k)}
names_B = {k: (v['name'] if isinstance(v, dict) else v) for k, v in NUMB.items() if re.fullmatch(r'\d+', k)}
for k in sorted(set(names_A) & set(names_B), key=int):
    if clean(names_A[k]) != clean(names_B[k]):
        add('标记名称', f'标记 {k}', f'numerals.json「{names_A[k]}」', f'numerals_structure.json「{names_B[k]}」',
            '一号一名：统一两表名称（构建脚本取前者，图8/图10 引线所指部件须与该名称一致）')
# 名称重复（不同号同名）
inv = {}
for k, n in NAME.items(): inv.setdefault(n, []).append(k)
for n, ks in inv.items():
    if len(ks) > 1:
        add('标记名称', f'标记 {",".join(ks)}', f'同名「{n}」', '一号一名', '区分名称')
# roles.js 引用的号必须存在
for r, k in ROLES.items():
    if str(k) not in NAME:
        add('标记', f'roles.js 角色「{r}」', str(k), 'numerals*.json 无此号', '补号或改映射')
# 附图实际标记
FIGLAB = {}
for f in FIGS:
    base = ROOT / f[2]
    jf = Path(str(base) + '.json')
    if jf.exists():
        FIGLAB[FIGS.index(f) + 1] = [str(x) for x in loadj(jf).get('labels', [])]
    elif not Path(str(base) + '.png').exists():
        add('附图', f'roles.js FIGS 第{FIGS.index(f) + 1}幅', f[2], '文件不存在', '补图或改路径')
all_fig = set(x for v in FIGLAB.values() for x in v)
for k in sorted(all_fig, key=int):
    if k not in NAME:
        add('标记', f'附图中标记 {k}', k, 'numerals 表无此号', '补')
# 与 numerals fig 字段一致性
for tab, tname in ((NUMA, 'numerals.json'), (NUMB, 'numerals_structure.json')):
    for k, v in tab.items():
        if not re.fullmatch(r'\d+', k) or not isinstance(v, dict): continue
        for n in v.get('fig', []):
            if n in FIGLAB and k not in FIGLAB[n]:
                add('标记', f'{tname} 标记 {k}', f'fig 字段含图{n}', f'图{n}.json labels 无 {k}', '同步 fig 字段或补引线')
# 文本使用的标记
used = set()
for doc in ('摘要', '权利要求', '说明书'):
    for loc, raw, txt in DOCS.get(doc, []):
        used |= set(k for k in re.findall(r'\{[~#]?(\d+)\}', raw) if k in NAME)
if exp.exists():
    E = loadj(exp)
    used |= set(map(str, E.get('used_labels', [])))
    for n, labs in (E.get('fig_labels') or {}).items():
        FIGLAB[int(n)] = [str(x) for x in labs]
    all_fig = set(x for v in FIGLAB.values() for x in v)
if DOCS.get('说明书'):
    for k in sorted(used - all_fig, key=int):
        add('标记', f'文本标记 {k}「{NAME.get(k, "?")}」', '文中使用', '任何附图均未标出', '在附图中加引线，或文中改为不带标记')
    for k in sorted(all_fig - used, key=int):
        add('标记', f'附图标记 {k}「{NAME.get(k, "?")}」', '附图中有', '说明书/权利要求未使用', '说明书中补述或删引线')
    # 附图说明引用每幅图
    desc_txt = ' '.join(t for _, _, t in DOCS['说明书'])
    raw_desc = ' '.join(r for _, r, _ in DOCS['说明书'])
    for i, f in enumerate(FIGS, 1):
        if not re.search(rf'图{i}(?!\d)', desc_txt) and ('{%' + f[0] + '}') not in raw_desc:
            add('附图', f'图{i}（{f[1]}）', '—', '说明书未引用', '附图说明及实施例中引用')
    if 'TODO' in desc_txt:
        for loc, raw, t in DOCS['说明书']:
            if 'TODO' in t: add('占位', loc, re.search(r'TODO\([^)]*\)', t).group(0), '数据未读到', '补数据')
# 附图清单图号一致
qd = (ROOT / '05_附图/附图_清单.md').read_text(encoding='utf-8')
if FIGS and '图16' in qd and len(FIGS) != 18:
    m16 = [f for f in FIGS if '图16' in f[2]]
    if m16:
        add('附图', '05_附图/附图_清单.md', '仿真曲线记为 图16~图18、图11~15 预留',
            f'roles.js 将其排为图{FIGS.index(m16[0]) + 1}~图{len(FIGS)}（共 {len(FIGS)} 幅）', '更新附图清单图号，或在申请文本中保持一致')
# 交底书中的“附图标记 名称”一致性：如 “尾座液压缸 26”
for loc, raw, txt in DOCS.get('交底书', []):
    for m in re.finditer(r'([一-龥]{2,12})\s*[（(]?(\d{1,2})[)）]?(?=[、，,；;。\s）)]|$)', txt):
        n, k = m.group(1), m.group(2)
        if k in NAME and re.search(r'[阀缸器泵机箱块座套尖筒轨架板身盘杠罩门关塞杆盖腔道芯圈头站孔锁]$', n):
            nm = NAME[k]
            if nm[-2:] not in n and n[-2:] not in nm and not any(a in n for a in [nm[:2], nm[-2:]]):
                add('术语', loc, f'{n} {k}', f'标记表 {k}=「{nm}」', '核对名称/编号')

# 定向复核：说明书中的结论性数值
xs = [lock(x)['Kd'] for x in range(20, 131)]
kmin = min(xs); xmin = 20 + xs.index(kmin)
for doc in ('说明书', '交底书'):
    for loc, raw, txt in DOCS.get(doc, []):
        m = re.search(r'整个顶紧位置范围内[^。]*?不低于\s*(\d+\.?\d*)\s*N/[µμu]m', txt)
        if m and float(m.group(1)) > kmin + 0.05:
            add('算例', loc, m.group(0), f'复算 x=20~130 mm 双腔串联刚度最小 {kmin:.2f} N/µm（x≈{xmin} mm），额定 70 mm 处 {L70["Kd"]:.2f}', f'改为“不低于{math.floor(kmin*10)/10:.1f} N/μm”或“约45 N/μm”')
        for m in re.finditer(r'ΔL=\((\d+)[−-](\d+\.?\d*)\)/(\d+\.?\d*)=(\d+\.\d+)', txt):
            a, b_, c, r = map(float, m.groups()); v = (a - b_) / c; nd = len(m.group(4).split('.')[1])
            if round(v, nd) != r:
                add('算例', loc, m.group(0), f'按文中数值复算 {(a-b_)}/{c}={v:.4f}（用未取整 K={L70["Kd"]:.2f} 为 {(a-b_)/L70["Kd"]:.3f}）', f'改为 {v:.{nd}f} μm，或写“≈5.6 μm”')
        m = re.search(r'约回复\s*(\d+)\s*次', txt)
        if m:
            SC = loadj(ROOT / '03_仿真验证/数据/scen.json')
            c1 = [v for k, v in SC['工况'].items() if k.startswith('C1')][0]['M2']['动作次数']
            est = DER['伸长57.5推力双'] / (0.05 * F0)
            if abs(int(m.group(1)) - c1) > 2:
                add('跨文档', loc, m.group(0) + f'（静态估算 {est:.1f} 次）', f'scen.json C1 M2 动作次数 {c1}（表2 同）', '注明为忽略油温/回复超调的粗估，或与表2 对齐说明差异原因')

# 交底书 vs 申请文本：权利要求项数
if src.get('claims'):
    nc = len(src['claims'])
    for loc, raw, txt in DOCS.get('交底书', []):
        m = re.search(r'共\s*(\d+)\s*项', txt)
        if m and int(m.group(1)) != nc:
            add('跨文档', loc, m.group(0), f'patent_text.js 权利要求 {nc} 项', '统一')
        for mm in re.finditer(r'(系统|试验台|方法)独权\s*(\d+)', txt):
            pass

# ------------------------------------------------------------------ 写报告
rnd = None
if '--round' in sys.argv: rnd = int(sys.argv[sys.argv.index('--round') + 1])
outdir = ROOT / '10_审查与迭代'
if rnd is None:
    ex = [int(re.search(r'第(\d+)轮', p.name).group(1)) for p in outdir.glob('数值一致性审计_第*轮.md')]
    rnd = max(ex, default=0) + 1
# 去重
seen = set(); uniq = []
for it in issues:
    key = (it[0], it[2], it[3])
    if key in seen: continue
    seen.add(key); uniq.append(it)
L = [f'# 数值一致性审计 第{rnd}轮（R3）', '',
     f'时间：{datetime.datetime.now():%Y-%m-%d %H:%M}；脚本：07_脚本/audit_numbers.py；只读审计。', '',
     '读到的文本：' + '、'.join(f'{k}（{len(v)}段/行）' for k, v in DOCS.items()) + f'；06_申请文件/_expanded.json：{"有" if exp.exists() else "无"}。', '',
     f'不一致/待核共 {len(uniq)} 处。', '']
L += ['## 算例复算（基准参数，x=70 mm）', '',
      f'A1={A1:.1f} mm²，A2={A2:.1f} mm²；V1={L70["V1"]:.1f} cm³，V2={L70["V2"]:.1f} cm³；k1={L70["k1"]:.2f}，k2={L70["k2"]:.2f} N/µm；'
      f'K单={L70["Ks"]:.2f}，K双={L70["Kd"]:.2f} N/µm；热漂移 单={L70["Ts"]:.0f}，双={L70["Td"]:.1f} N/K；'
      f'p1_set(6000)={p1set(6000):.3f} MPa；F_L/F_H/F_safe={DER["FL"]:.0f}/{DER["FH"]:.0f}/{DER["Fsafe"]:.0f} N；'
      f'57.5 µm 伸长推力增量 单={DER["伸长57.5推力单"]:.0f} N、双={DER["伸长57.5推力双"]:.0f} N；单腔漂移/F0={DER["漂移单/F0%"]:.1f}%。', '']
L += ['## 不一致清单', '', '| # | 类别 | 位置 | 文中值 | 真值源及其值 | 建议 |', '|---|---|---|---|---|---|']
for i, (c, loc, t, tr, s) in enumerate(uniq, 1):
    esc = lambda x: str(x).replace('|', '／').replace('\n', ' ')
    L.append(f'| {i} | {esc(c)} | {esc(loc)} | {esc(t)} | {esc(tr)} | {esc(s)} |')
if notes:
    L += ['', '## 备注', ''] + [f'- {n}' for n in notes]
out = outdir / f'数值一致性审计_第{rnd}轮.md'
out.write_text('\n'.join(L) + '\n', encoding='utf-8')
print(f'第{rnd}轮 不一致 {len(uniq)} 处 -> {out}')
print(json.dumps({'round': rnd, 'n': len(uniq), 'appfiles': exp.exists(),
                  'cats': {c: sum(1 for u in uniq if u[0] == c) for c in set(u[0] for u in uniq)}}, ensure_ascii=False))
