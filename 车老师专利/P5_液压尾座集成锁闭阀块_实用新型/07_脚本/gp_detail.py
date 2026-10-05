# -*- coding: utf-8 -*-
r"""P5 查新：逐篇读取 Google Patents 详情页（摘要、权利要求 1、申请人、日期、PDF 链接），请求间隔 ≥20 s。

用法：.venv\Scripts\python.exe 07_脚本\gp_detail.py CN202381448U EP2761189A1 ...  [--pdf]
输出：01_查新与创新点\检索原始结果\detail_<公开号>.json；--pdf 时把全文 PDF 存到 01_查新与创新点\文献\
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "01_查新与创新点", "检索原始结果")
PDFDIR = os.path.join(ROOT, "01_查新与创新点", "文献")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PDFDIR, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    b = urllib.request.urlopen(req, timeout=60).read()
    return b if binary else b.decode("utf-8", "replace")


def strip(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def meta(h, name):
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), h)
    return html.unescape(m.group(1)) if m else None


def metas(h, name):
    return [html.unescape(x) for x in re.findall(r'<meta name="%s" content="([^"]*)"' % re.escape(name), h)]


def detail(pn, lang):
    url = "https://patents.google.com/patent/%s/%s" % (pn, lang)
    h = get(url)
    ab = re.search(r'<section itemprop="abstract"[^>]*>(.*?)</section>', h, re.S)
    cl = re.search(r'<section itemprop="claims"[^>]*>(.*?)</section>', h, re.S)
    claims = strip(cl.group(1)) if cl else ""
    pdf = re.search(r'href="(https://patentimages\.storage\.googleapis\.com/[^"]+\.pdf)"', h)
    pri = re.search(r'itemprop="priorityDate">([^<]+)<', h)
    fil = re.search(r'itemprop="filingDate">([^<]+)<', h)
    pub = re.search(r'itemprop="publicationDate">([^<]+)<', h)
    assg = re.findall(r'itemprop="assigneeOriginal"[^>]*>([^<]+)<', h)
    inv = re.findall(r'itemprop="inventor"[^>]*>([^<]+)<', h)
    return {
        "公开号": pn, "链接": url, "标题": meta(h, "DC.title"), "原始申请人": [a.strip() for a in assg],
        "发明人": [i.strip() for i in inv][:8], "优先权日": pri.group(1) if pri else None,
        "申请日": fil.group(1) if fil else None, "公开日": pub.group(1) if pub else None,
        "摘要": strip(ab.group(1))[:1500] if ab else meta(h, "DC.description"),
        "权利要求_前1500字": claims[:1500], "PDF": pdf.group(1) if pdf else None,
        "读取时间": time.strftime("%Y-%m-%d %H:%M"),
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_pdf = "--pdf" in sys.argv
    for i, pn in enumerate(args):
        if i:
            time.sleep(20)
        lang = "zh" if pn.startswith("CN") else "en"
        try:
            d = detail(pn, lang)
        except Exception as e:  # noqa: BLE001
            print(pn, "ERR", e, flush=True)
            continue
        if want_pdf and d["PDF"]:
            try:
                time.sleep(3)
                b = get(d["PDF"], binary=True)
                fn = os.path.join(PDFDIR, pn + ".pdf")
                with open(fn, "wb") as fh:
                    fh.write(b)
                d["PDF本地"] = "文献/" + pn + ".pdf"
            except Exception as e:  # noqa: BLE001
                d["PDF本地"] = "下载失败：%s" % e
        with open(os.path.join(OUT, "detail_%s.json" % pn), "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        print(pn, "ok |", (d["标题"] or "")[:60], "|", d["原始申请人"][:2], "|", d["优先权日"], flush=True)
