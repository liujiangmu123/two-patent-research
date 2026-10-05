# -*- coding: utf-8 -*-
"""Markdown → Word（报告类文档：调研报告、查新报告、技术交底书、仿真验证报告、设计规格书、自查清单）。

支持：# 标题（1–4 级）、段落、无序/有序列表、> 引用、| 表格 |、![图题](相对路径) 图片、```代码块```、
**粗体**、`代码`、$...$ 行内公式（原样保留为斜体文本）。中文宋体、西文 Times New Roman，正文小四，1.5 倍行距，
A4 页边距 25/20 mm，页脚页码。可选 --toc 在标题后插入目录域（用 Word COM 更新）。
用法：.venv\\Scripts\\python.exe md2docx.py <a.md> [<b.md> ...] [--toc] [--title 封面标题]
输出：同名 .docx。
"""
import argparse
import os
import re

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING_RULE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\$[^$]+\$|\*[^*\s][^*]*\*)")


def set_font(run, east="宋体", west="Times New Roman", size=None, bold=None, italic=None, color=None):
    run.font.name = west
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), east)
    rfonts.set(qn("w:ascii"), west)
    rfonts.set(qn("w:hAnsi"), west)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_inline(par, text, size=12, bold=False):
    for tok in INLINE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            set_font(par.add_run(tok[2:-2]), size=size, bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            set_font(par.add_run(tok[1:-1]), east="宋体", west="Consolas", size=size - 1.5, bold=bold)
        elif tok.startswith("$") and tok.endswith("$"):
            set_font(par.add_run(tok[1:-1]), size=size, italic=True, bold=bold)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            set_font(par.add_run(tok[1:-1]), size=size, italic=True, bold=bold)
        else:
            set_font(par.add_run(tok), size=size, bold=bold)


def para_fmt(p, first_indent=True, align=None, before=0, after=0):
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING_RULE.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if first_indent:
        pf.first_line_indent = Pt(24)
    if align is not None:
        p.alignment = align


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for code in ("PAGE",):
        r = p.add_run()
        f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = code
        f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
        r._r.append(f1); r._r.append(it); r._r.append(f2)
        set_font(r, size=10.5)


def add_toc(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = 'TOC \\o "1-3" \\h \\z \\u'
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = "（目录：在 Word 中右键“更新域”）"
    f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "end")
    for el in (f1, it, f2, t, f3):
        r._r.append(el)
    doc.add_page_break()


def shade(cell, hexcolor="D9D9D9"):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)


def convert(md_path, toc=False, title=None):
    base = os.path.dirname(os.path.abspath(md_path))
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.top_margin = sec.bottom_margin = Mm(25)
    sec.left_margin = sec.right_margin = Mm(22)
    add_page_number(sec)
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    st.font.size = Pt(12)
    for lvl, sz in ((1, 16), (2, 14), (3, 13), (4, 12)):
        hs = doc.styles[f"Heading {lvl}"]
        hs.font.name = "Times New Roman"
        hs.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        hs.font.size = Pt(sz)
        hs.font.bold = True
        hs.font.color.rgb = RGBColor(0, 0, 0)
    lines = open(md_path, encoding="utf-8").read().splitlines()
    i = 0
    first_h1 = True
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            p = doc.add_paragraph()
            para_fmt(p, first_indent=False)
            p.paragraph_format.line_spacing = 1.0
            for k, b in enumerate(buf):
                r = p.add_run(b + ("\n" if k < len(buf) - 1 else ""))
                set_font(r, east="宋体", west="Consolas", size=9)
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", x) for x in cells if x):
                    rows.append(cells)
                i += 1
            ncol = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=ncol)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r_i, row in enumerate(rows):
                for c_i in range(ncol):
                    txt = row[c_i] if c_i < len(row) else ""
                    cell = t.cell(r_i, c_i)
                    cell.text = ""
                    p = cell.paragraphs[0]
                    p.paragraph_format.line_spacing = 1.15
                    add_inline(p, txt.replace("<br>", "\n"), size=10, bold=(r_i == 0))
                    if r_i == 0:
                        shade(cell)
            doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            txt = m.group(2).strip()
            if lvl == 1 and first_h1:
                p = doc.add_paragraph()
                para_fmt(p, first_indent=False, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=12)
                set_font(p.add_run(title or txt), east="黑体", size=18, bold=True)
                first_h1 = False
                if toc:
                    add_toc(doc)
            else:
                h = doc.add_heading(level=min(lvl, 4) if lvl > 1 else 1)
                set_font(h.add_run(txt), east="黑体", size={1: 16, 2: 14, 3: 13, 4: 12}[min(lvl, 4)], bold=True, color=(0, 0, 0))
            i += 1
            continue
        mi = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", s)
        if mi:
            cap, rel = mi.group(1), mi.group(2)
            pth = os.path.normpath(os.path.join(base, rel))
            if os.path.exists(pth):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(pth, width=Cm(15.5))
                c = doc.add_paragraph()
                para_fmt(c, first_indent=False, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
                set_font(c.add_run(cap), size=10.5)
            else:
                p = doc.add_paragraph()
                set_font(p.add_run(f"[缺图：{rel}]"), size=10.5, color=(200, 0, 0))
            i += 1
            continue
        if not s:
            i += 1
            continue
        if s.startswith(">"):
            p = doc.add_paragraph()
            para_fmt(p, first_indent=False)
            p.paragraph_format.left_indent = Cm(0.8)
            add_inline(p, s.lstrip("> ").strip(), size=10.5)
            i += 1
            continue
        mb = re.match(r"^(\s*)([-*+]|\d+[.)、])\s+(.*)$", ln)
        if mb:
            indent = len(mb.group(1)) // 2
            p = doc.add_paragraph()
            para_fmt(p, first_indent=False)
            p.paragraph_format.left_indent = Cm(0.75 + 0.6 * indent)
            p.paragraph_format.first_line_indent = Cm(-0.5)
            bullet = "• " if mb.group(2) in "-*+" else mb.group(2) + " "
            add_inline(p, bullet + mb.group(3))
            i += 1
            continue
        p = doc.add_paragraph()
        para_fmt(p)
        add_inline(p, s)
        i += 1
    out = os.path.splitext(md_path)[0] + ".docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="+")
    ap.add_argument("--toc", action="store_true")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    for f in a.md:
        print("写出", convert(f, toc=a.toc, title=a.title))
