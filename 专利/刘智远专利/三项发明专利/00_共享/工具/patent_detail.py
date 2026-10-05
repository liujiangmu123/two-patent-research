# -*- coding: utf-8 -*-
"""Fetch abstract + independent claim of the closest prior-art patents from Google Patents."""
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "patent_details.md"
NUMS = sys.argv[1:] or [
    "CN121053109A", "CN120852641A", "CN121432427A", "CN117933030B", "CN115310172A",
    "CN121365540A", "CN118627333A", "CN121561328A", "CN115222883B", "CN119723557A",
    "CN119861381A", "CN116930964A", "CN120976438A", "CN121482007A",
]


def fetch(no):
    url = f"https://patents.google.com/patent/{no}/zh"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        page = r.read().decode("utf-8", "ignore")
    title = re.search(r'<meta name="DC.title" content="([^"]*)"', page)
    abstract = re.search(r'<meta name="DC.description" content="([^"]*)"', page)
    claims = re.search(r'<section itemprop="claims".*?</section>', page, re.S)
    ctext = ""
    if claims:
        ctext = re.sub(r"<[^>]+>", " ", claims.group(0))
        ctext = re.sub(r"\s+", " ", html.unescape(ctext)).strip()
    status = re.search(r'itemprop="legalStatusIfi"[^>]*>\s*([^<]+)<', page)
    return {
        "title": html.unescape(title.group(1)).strip() if title else "",
        "abstract": html.unescape(abstract.group(1)).strip() if abstract else "",
        "claim1": ctext[:1400],
        "status": status.group(1).strip() if status else "",
    }


def main():
    lines = ["# 最接近现有技术专利详情（Google Patents 自动抓取）\n"]
    for no in NUMS:
        try:
            d = fetch(no)
        except Exception as e:
            lines.append(f"\n## {no}\n抓取失败：{e}\n")
            print("FAIL", no, e)
            continue
        lines.append(f"\n## {no} {d['title']}（{d['status']}）\n\n摘要：{d['abstract']}\n\n权利要求（节选）：{d['claim1']}\n")
        print("ok", no, d["title"][:40], d["status"])
        time.sleep(1.2)
    OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
