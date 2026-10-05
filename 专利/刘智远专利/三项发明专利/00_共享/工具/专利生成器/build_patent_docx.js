// -*- coding: utf-8 -*-
// 通用发明专利申请文件生成器（Node + docx），由参考专利 V11/V12 生成器改写为“按专利文件夹”调用。
// 用法（PowerShell）：
//   $env:NODE_PATH=(npm root -g); node <本文件> --root <专利文件夹> [--text 文本源.js] [--desc 说明书源.js] [--num numerals.json] [--nfig N]
//   默认：文本源 <root>/08_脚本/patent_text.js，说明书源 <root>/08_脚本/patent_desc.js，标记表 <root>/08_脚本/numerals.json，
//         附图 <root>/06_附图/标注版/图N.png + 图N.json（N 自 1 连续自动计数），输出 <root>/07_申请文件/。
// 文本源导出：{ fullTitle, abstract, abstractFigure, claims:[{id, paras:[...]}] }；说明书源导出：{ description:[...] }。
// 记号：{12} 名称+标记（权利要求书“名称（12）”，说明书“名称12”）；{~12} 仅名称；{#12} 仅标记；{@c3} 引用权利要求编号；
//       **X** 粗斜体；*x* 斜体；_{..} 下标；^{..} 上标；EQ 段落中单个拉丁/希腊字母自动斜体。
// 说明书条目：字符串或 {t:'p'|'sh'|'h'|'eq'|'table'|'labels', ...}（见 helpers.js）。
// 输出：发明专利申请文件_全文.docx + 说明书摘要/摘要附图/权利要求书/说明书/说明书附图.docx + _expanded.json（供 check_patent.py 校验）。
'use strict';
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Header, Footer, AlignmentType, PageNumber, TabStopType,
  LineRuleType, Tab, Table, TableRow, TableCell, WidthType, BorderStyle, VerticalAlign, TableLayoutType,
} = require('docx');

const ARGS = {};
for (let i = 2; i < process.argv.length; i += 2) ARGS[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
if (!ARGS.root) { console.error('缺少 --root <专利文件夹>'); process.exit(2); }
const ROOT = path.resolve(ARGS.root);
const SCR = path.join(ROOT, '08_脚本');
const FIGDIR = path.join(ROOT, '06_附图', '标注版');
const OUTDIR = path.join(ROOT, '07_申请文件');
fs.mkdirSync(OUTDIR, { recursive: true });

const TXT = require(path.resolve(ARGS.text || path.join(SCR, 'patent_text.js')));
const { description } = require(path.resolve(ARGS.desc || path.join(SCR, 'patent_desc.js')));
const NUM = JSON.parse(fs.readFileSync(path.resolve(ARGS.num || path.join(SCR, 'numerals.json')), 'utf8'));

// 权利要求：兼容旧格式（段落数组）与新格式（{id, paras}），{@id} 换算为编号
const CLAIMS = TXT.claims.map((c, i) => (Array.isArray(c) ? { id: 'c' + (i + 1), paras: c } : c));
const CID = Object.fromEntries(CLAIMS.map((c, i) => [c.id, i + 1]));
const resolveRefs = (s) => s.replace(/\{@(\w+)\}/g, (m, id) => {
  if (!(id in CID)) throw new Error('未知权利要求引用 ' + id);
  return String(CID[id]);
});

// ---------------------------------------------------------------- 附图与可用附图标记
let NFIG = ARGS.nfig ? parseInt(ARGS.nfig, 10) : 0;
if (!NFIG) { while (fs.existsSync(path.join(FIGDIR, `图${NFIG + 1}.json`))) NFIG += 1; }
if (!NFIG) { console.error('未找到附图 ' + path.join(FIGDIR, '图1.json')); process.exit(2); }
const FIGS = [];
const USED = new Set();
for (let n = 1; n <= NFIG; n++) {
  const j = JSON.parse(fs.readFileSync(path.join(FIGDIR, `图${n}.json`), 'utf8'));
  const png = path.join(FIGDIR, `图${n}.png`);
  const buf = fs.readFileSync(png);
  const wpx = buf.readUInt32BE(16), hpx = buf.readUInt32BE(20);
  let labels = j.labels || [];
  if (!Array.isArray(labels)) labels = Object.keys(labels);
  labels = labels.map(String).filter((k) => /^\d+[A-Za-z]?$/.test(k));
  labels.forEach((k) => { if (!NUM[k]) throw new Error(`图${n}.json 的标记 ${k} 不在 numerals.json 中`); });
  FIGS.push({ n, labels, png, buf, wpx, hpx, size_mm: j.size_mm, title: j.title || '' });
  labels.forEach((l) => USED.add(l));
}
const nameOf = (k) => {
  if (!USED.has(k)) throw new Error(`附图标记 ${k}（${NUM[k] ? NUM[k].name : '未定义'}）未出现在任何附图中`);
  return NUM[k].name;
};

// ---------------------------------------------------------------- 版式常量（A4，上 25、下 15、左 25、右 15 mm）
const TW_MM = 1440 / 25.4;
const PAGE = { width: 11906, height: 16838 };
const MARGIN = { top: Math.round(25 * TW_MM), bottom: Math.round(15 * TW_MM), left: Math.round(25 * TW_MM),
  right: Math.round(15 * TW_MM), header: Math.round(12 * TW_MM), footer: Math.round(6 * TW_MM), gutter: 0 };
const TEXT_W = PAGE.width - MARGIN.left - MARGIN.right;       // 9639 twip = 170 mm
const BODY = 24;                                               // 小四 12 pt（半磅）
const SONG = { ascii: 'Times New Roman', hAnsi: 'Times New Roman', eastAsia: '宋体', cs: 'Times New Roman' };
const HEI = { ascii: 'Times New Roman', hAnsi: 'Times New Roman', eastAsia: '黑体', cs: 'Times New Roman' };
const LINE15 = { line: 360, lineRule: LineRuleType.AUTO, before: 0, after: 0 };
const LINE1 = { line: 240, lineRule: LineRuleType.AUTO, before: 0, after: 0 };
const IND2 = { firstLine: 2 * 240 };
const MM2PX = (mm) => Math.round(mm / 25.4 * 96);
const DPI = parseFloat(ARGS.dpi || '400');                     // 附图 PNG 的标称分辨率

// ---------------------------------------------------------------- 富文本解析
const FUNCS = /^(arctan|arcsin|arccos|cos|sin|tan|exp|log|ln|det|tr|max|min|arg|diag|sign|rank|cond|var|cov|std)/;
function autoItal(s, base, out) {
  let i = 0;
  let buf = '';
  const flush = () => { if (buf) { out.push({ ...base, text: buf }); buf = ''; } };
  while (i < s.length) {
    const m = s.slice(i).match(FUNCS);
    if (m && !/[A-Za-z]/.test(s[i - 1] || '')) { buf += m[1]; i += m[1].length; continue; }
    const c = s[i];
    if (/[A-Za-z\u03b1-\u03c9\u0391-\u03a9]/.test(c)) {
      flush();
      out.push({ ...base, text: c, i: true });
    } else buf += c;
    i++;
  }
  flush();
}

function parseRich(src, mode, ctx, eq = false) {
  const out = [];
  const re = /\{([~#]?)(\d+[A-Za-z]?)\}|\*\*([^*]+)\*\*|\*([^*]+)\*|_\{([^}]*)\}|\^\{([^}]*)\}/g;
  let last = 0;
  let m;
  const plain = (s) => {
    if (!s) return;
    if (eq) autoItal(s, {}, out);
    else out.push({ text: s });
  };
  while ((m = re.exec(src)) !== null) {
    plain(src.slice(last, m.index));
    if (m[2] !== undefined) {
      const k = m[2];
      const nm = nameOf(k);
      ctx.nums.add(k);
      if (m[1] === '~') out.push({ text: nm });
      else if (m[1] === '#') out.push({ text: mode === 'claim' ? `（${k}）` : k });
      else out.push({ text: mode === 'claim' ? `${nm}（${k}）` : `${nm}${k}` });
      ctx.tokens.push({ k, form: m[1] || 'full' });
    } else if (m[3] !== undefined) {
      out.push({ text: m[3], i: true, b: true });
    } else if (m[4] !== undefined) {
      out.push({ text: m[4], i: true });
    } else if (m[5] !== undefined) {
      autoItal(m[5], { sub: true }, out);
    } else if (m[6] !== undefined) {
      autoItal(m[6], { sup: true }, out);
    }
    last = re.lastIndex;
  }
  plain(src.slice(last));
  return out;
}
const segText = (segs) => segs.map((s) => s.text).join('');

function runs(segs, font = SONG, size = BODY, extra = {}) {
  return segs.map((s) => new TextRun({
    text: s.text, font, size, italics: !!s.i, bold: !!s.b || !!extra.bold,
    subScript: !!s.sub, superScript: !!s.sup,
  }));
}

// ---------------------------------------------------------------- 页眉页脚
const spaced = (t) => t.split('').join('\u3000');
function header(partTitle) {
  return new Header({ children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: LINE1,
    children: [new TextRun({ text: spaced(partTitle), font: HEI, size: 32 })] })] });
}
function footer() {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: LINE1,
    children: [new TextRun({ children: [PageNumber.CURRENT, '/', PageNumber.TOTAL_PAGES_IN_SECTION], font: SONG, size: 21 })] })] });
}
function section(partTitle, children) {
  return {
    properties: { page: { size: PAGE, margin: MARGIN, pageNumbers: { start: 1 } } },
    headers: { default: header(partTitle) },
    footers: { default: footer() },
    children,
  };
}

// ---------------------------------------------------------------- 各部分
const EXP = { title: TXT.fullTitle, abstract: '', claims: [], description: [], figures: [] };

function buildAbstract() {
  const ctx = { nums: new Set(), tokens: [] };
  const segs = parseRich(TXT.abstract, 'claim', ctx);
  EXP.abstract = segText(segs);
  return [new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: IND2, spacing: LINE15, children: runs(segs) })];
}

function imagePara(fig, scale, opts = {}) {
  const wmm = fig.wpx / DPI * 25.4 * scale;
  const hmm = fig.hpx / DPI * 25.4 * scale;
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: LINE1, keepNext: true, pageBreakBefore: !!opts.pageBreakBefore,
    children: [new ImageRun({ type: 'png', data: fig.buf, transformation: { width: MM2PX(wmm), height: MM2PX(hmm) },
      altText: { title: `图${fig.n}`, description: fig.title, name: `图${fig.n}` } })],
  });
}

function fitScale(fig, maxW, maxH) {
  const wmm = fig.wpx / DPI * 25.4, hmm = fig.hpx / DPI * 25.4;
  return Math.min(1.0, maxW / wmm, maxH / hmm);
}

function buildAbstractFigure() {
  const fig = FIGS[(TXT.abstractFigure || 1) - 1];
  return [imagePara(fig, Math.min(0.70, fitScale(fig, 150, 200)))];
}

function buildClaims() {
  const out = [];
  CLAIMS.forEach((cl, idx) => {
    const no = idx + 1;
    const ctx = { nums: new Set(), tokens: [] };
    const paras = cl.paras.map((s) => parseRich(resolveRefs(s), 'claim', ctx));
    EXP.claims.push({ no, id: cl.id, text: `${no}. ` + paras.map(segText).join(''), paras: paras.map(segText), nums: [...ctx.nums] });
    paras.forEach((p, i) => {
      const lead = i === 0 ? [{ text: `${no}. ` }] : [];
      out.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: IND2, spacing: LINE15, children: runs(lead.concat(p)) }));
    });
  });
  return out;
}

function labelParas() {
  const keys = [...USED].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  const groups = {};
  keys.forEach((k) => { (groups[k[0]] = groups[k[0]] || []).push(k); });
  const gk = Object.keys(groups).sort();
  const items = [{ text: '附图中各附图标记如下：', nums: [] }];
  gk.forEach((g, gi) => {
    const list = groups[g].map((k) => `${k}、${NUM[k].name}`).join('；');
    items.push({ text: list + (gi === gk.length - 1 ? '。' : '；'), nums: groups[g] });
  });
  return items;
}

function buildDescription() {
  const out = [];
  let pno = 0;
  let part = '';
  const numbered = (children, opts = {}) => {
    pno += 1;
    const tag = `[${String(pno).padStart(4, '0')}]`;
    return { tag, para: new Paragraph({ alignment: opts.align || AlignmentType.JUSTIFIED, spacing: LINE15, tabStops: opts.tabStops,
      children: [new TextRun({ text: tag + (opts.noGap ? '' : '\u3000'), font: SONG, size: BODY })].concat(children) }) };
  };
  out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 360, lineRule: LineRuleType.AUTO, after: 120 },
    children: [new TextRun({ text: TXT.fullTitle, font: HEI, size: 30 })] }));
  for (const item of description) {
    const it = typeof item === 'string' ? { t: 'p', text: item } : item;
    if (it.t === 'h') {
      part = it.text;
      out.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: LINE15, keepNext: true,
        children: [new TextRun({ text: it.text, font: HEI, size: BODY })] }));
      EXP.description.push({ type: 'h', text: it.text });
      continue;
    }
    if (it.t === 'labels') {
      for (const L of labelParas()) {
        const { tag, para } = numbered([new TextRun({ text: L.text, font: SONG, size: BODY })]);
        out.push(para);
        EXP.description.push({ type: 'labels', no: tag, part, text: L.text, nums: L.nums });
      }
      continue;
    }
    const ctx = { nums: new Set(), tokens: [] };
    if (it.t === 'table') {
      out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 360, lineRule: LineRuleType.AUTO, before: 60 },
        keepNext: true, children: runs(parseRich(it.caption, 'desc', ctx), SONG, 21) }));
      const ncol = it.head.length;
      const first = it.firstColRatio || (ncol <= 2 ? 0.5 : ncol >= 6 ? 0.28 : 0.36);
      const colW = [Math.round(TEXT_W * first)];
      for (let c = 1; c < ncol; c++) colW.push(Math.round((TEXT_W - colW[0]) / (ncol - 1)));
      const B = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
      const cell = (txt, c, head) => new TableCell({
        width: { size: colW[c], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
        borders: { top: B, bottom: B, left: B, right: B },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ alignment: c === 0 && !head ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: LINE1,
          children: runs(parseRich(String(txt), 'desc', ctx), SONG, 21, { bold: head }) })],
      });
      const rowsAll = [it.head].concat(it.rows);
      rowsAll.forEach((r, ri) => { if (r.length !== ncol) throw new Error(`表格“${it.caption}”第 ${ri} 行列数 ${r.length} ≠ 表头 ${ncol}`); });
      out.push(new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: colW, layout: TableLayoutType.FIXED,
        rows: rowsAll.map((r, ri) => new TableRow({ tableHeader: ri === 0, cantSplit: true, children: r.map((t, c) => cell(t, c, ri === 0)) })) }));
      out.push(new Paragraph({ spacing: { line: 240, lineRule: LineRuleType.AUTO, after: 60 }, children: [] }));
      const flat = [it.caption].concat(rowsAll.map((r) => r.join(' | '))).join('\n');
      const segsFlat = parseRich(flat, 'desc', ctx);
      EXP.description.push({ type: 'table', part, text: segText(segsFlat), nums: [...ctx.nums] });
      continue;
    }
    if (it.t === 'eq') {
      const segs = parseRich(it.text, 'desc', ctx, true);
      const { tag, para } = numbered([new TextRun({ children: [new Tab()] })].concat(runs(segs),
        [new TextRun({ children: [new Tab()] }), new TextRun({ text: `（${it.no}）`, font: SONG, size: BODY })]),
      { align: AlignmentType.LEFT, noGap: true,
        tabStops: [{ type: TabStopType.CENTER, position: Math.round(TEXT_W / 2) }, { type: TabStopType.RIGHT, position: TEXT_W }] });
      out.push(para);
      EXP.description.push({ type: 'eq', no: tag, part, text: segText(segs), eqno: it.no, nums: [...ctx.nums] });
      continue;
    }
    const segs = parseRich(it.text, 'desc', ctx);
    const { tag, para } = numbered(runs(segs, SONG, BODY, { bold: it.t === 'sh' }));
    out.push(para);
    EXP.description.push({ type: it.t, no: tag, part, text: segText(segs), nums: [...ctx.nums] });
  }
  return out;
}

function buildFigures() {
  const out = [];
  const maxW = 170, maxH = 257 - 12;
  FIGS.forEach((fig, i) => {
    const s = fitScale(fig, maxW, maxH);
    const wmm = fig.wpx / DPI * 25.4, hmm = fig.hpx / DPI * 25.4;
    out.push(imagePara(fig, s, { pageBreakBefore: i > 0 }));
    out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: 360, lineRule: LineRuleType.AUTO, before: 120 },
      children: [new TextRun({ text: `图${fig.n}`, font: SONG, size: BODY })] }));
    EXP.figures.push({ n: fig.n, title: fig.title, labels: fig.labels, print_mm: [+(wmm * s).toFixed(1), +(hmm * s).toFixed(1)],
      size_mm_json: fig.size_mm, scale: +s.toFixed(3) });
  });
  return out;
}

// ---------------------------------------------------------------- 生成
const PARTS = [
  { key: '说明书摘要', build: buildAbstract },
  { key: '摘要附图', build: buildAbstractFigure },
  { key: '权利要求书', build: buildClaims },
  { key: '说明书', build: buildDescription },
  { key: '说明书附图', build: buildFigures },
];
const STYLES = { default: { document: { run: { font: SONG, size: BODY }, paragraph: { spacing: LINE15 } } } };
const META = { creator: '申请人', title: TXT.fullTitle, description: '发明专利申请文件' };

(async () => {
  const built = PARTS.map((p) => ({ ...p, children: p.build() }));
  const docs = [];
  docs.push(['发明专利申请文件_全文.docx', new Document({ ...META, styles: STYLES,
    sections: built.map((p) => section(p.key, p.children)) })]);
  for (const p of PARTS) {
    const saveExp = JSON.stringify(EXP);
    const children = p.build();
    Object.assign(EXP, JSON.parse(saveExp));
    docs.push([`${p.key}.docx`, new Document({ ...META, styles: STYLES, sections: [section(p.key, children)] })]);
  }
  for (const [name, doc] of docs) {
    const buf = await Packer.toBuffer(doc);
    fs.writeFileSync(path.join(OUTDIR, name), buf);
    console.log('写出', name, (buf.length / 1024).toFixed(0), 'KB');
  }
  EXP.used_labels = [...USED].sort();
  EXP.fig_labels = Object.fromEntries(FIGS.map((f) => [f.n, f.labels]));
  EXP.fig_titles = Object.fromEntries(FIGS.map((f) => [f.n, f.title]));
  fs.writeFileSync(path.join(OUTDIR, '_expanded.json'), JSON.stringify(EXP, null, 1), 'utf8');
  console.log('附图', NFIG, '幅；附图标记', USED.size, '个；权利要求', EXP.claims.length, '项；说明书段落',
    EXP.description.filter((d) => d.no).length, '段');
})().catch((e) => { console.error(e); process.exit(1); });
