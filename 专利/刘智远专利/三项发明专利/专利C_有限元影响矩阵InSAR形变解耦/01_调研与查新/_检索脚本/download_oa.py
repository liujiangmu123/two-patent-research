# -*- coding: utf-8 -*-
"""下载开放获取文献 PDF 到 ../文献/，并抽取纯文本到 ../_raw/txt/（仅供撰写报告时阅读）。

单文件上限 30 MB；失败记录到 ../_raw/download_log.json。
用法：.venv\\Scripts\\python.exe <本文件> [编号 ...]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
DOC = HERE.parent / "文献"
TXT = HERE.parent / "_raw" / "txt"
LOGF = HERE.parent / "_raw" / "download_log.json"
DOC.mkdir(exist_ok=True)
TXT.mkdir(parents=True, exist_ok=True)
CAP = 30 * 1024 * 1024
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ITEMS = [
    ("L01", "EGU26-11441_Ma2026_UHV塔_复成一号_CR_PS仿真.pdf",
     "https://meetingorganizer.copernicus.org/EGU26/EGU26-11441.html?pdf"),
    ("L02", "RS2022_14_6261_Okgye矿区PSInSAR_塔热胀季节振荡.pdf",
     "https://www.mdpi.com/2072-4292/14/24/6261/pdf"),
    ("L03", "GeoHazards2025_6_83_采空区特高压塔差异沉降.pdf",
     "https://www.mdpi.com/2624-795X/6/4/83/pdf"),
    ("L04", "RS2017_9_648_Garthwaite_角反射器设计.pdf",
     "https://www.mdpi.com/2072-4292/9/7/648/pdf"),
    ("L05", "RS2018_10_86_Garthwaite_角反射器设计_勘误.pdf",
     "https://www.mdpi.com/2072-4292/10/1/86/pdf"),
    ("L06", "Fringe2023_NGET_输电资产角反射器.pdf",
     "https://fringe2023.esa.int/iframe-agenda/files/presentation-170.pdf"),
    ("L07", "WhiteRose_角反射器阵列_关键基础设施.pdf",
     "https://eprints.whiterose.ac.uk/id/eprint/191734/1/Novel_Corner-Reflector_Array_Application_in_Essential_Infrastructure_Monitoring.pdf"),
    ("L08", "HNU_钢桁拱桥PSI_温度场修正.pdf",
     "https://hnutest.hnu.edu.cn/pdf/Longtermdeformation.pdf"),
    ("L09", "ISPRS_Annals2026_铁路桥InSAR_FEM_热效应.pdf",
     "https://isprs-annals.copernicus.org/articles/XI-3-2026/455/2026/isprs-annals-XI-3-2026-455-2026.pdf"),
    ("L10", "RS2018_10_1714_两座桥Sentinel1热膨胀.pdf",
     "https://www.mdpi.com/2072-4292/10/11/1714/pdf"),
    ("L11", "IGARSS2014_Goel_热膨胀监测.pdf",
     "https://elib.dlr.de/97418/1/IGARSS_2014_Goel.pdf"),
    ("L12", "RS2019_11_1258_桥梁XC波段挠度与热膨胀.pdf",
     "https://www.mdpi.com/2072-4292/11/11/1258/pdf"),
    ("L13", "Sensors2024_24_7604_复成一号时序InSAR能力.pdf",
     "https://www.mdpi.com/1424-8220/24/23/7604/pdf"),
    ("L14", "RS2026_18_304_复成一号滑坡时序.pdf",
     "https://www.mdpi.com/2072-4292/18/2/304/pdf"),
    ("L15", "RS2026_18_1214_电子角反射器ECR业务化PSI.pdf",
     "https://www.mdpi.com/2072-4292/18/8/1214/pdf"),
    ("L16", "JGS2024_紧凑有源应答器CAT野外测试.pdf",
     "https://www.degruyterbrill.com/document/doi/10.1515/jogs-2022-0164/pdf?licenseType=open-access"),
    ("L17", "RS2021_13_926_GECORIS角反射器时序工具.pdf",
     "https://www.mdpi.com/2072-4292/13/5/926/pdf"),
    ("L18", "RS2023_15_5242_桥梁InSAR结构解释.pdf",
     "https://www.mdpi.com/2072-4292/15/21/5242/pdf"),
    ("L19", "Tonelli2024_桥梁InSAR贝叶斯融合.pdf",
     "https://iris.unitn.it/retrieve/91533c6c-bc91-4534-b258-352a6e177753/TonelliEtAl.2024_354_manuscript.pdf"),
    ("L20", "RS2023_15_4805_盐湖区塔基沉降预测.pdf",
     "https://www.mdpi.com/2072-4292/15/19/4805/pdf"),
    ("L21", "AppliedSci2025_15_11091_采动区输电塔稳定.pdf",
     "https://www.mdpi.com/2076-3417/15/20/11091/pdf"),
    ("L22", "RS2026_18_180_陆探一号图像质量.pdf",
     "https://www.mdpi.com/2072-4292/18/1/180/pdf"),
    ("L23", "ISPRS2024_陆探一号冻土走廊.pdf",
     "https://d-nb.info/1329608399/34"),
    ("L24", "RS2024_16_3457_复成一号矿区沉降.pdf",
     "https://www.mdpi.com/2072-4292/16/18/3457/pdf"),
    ("L25", "SCIS2025_复成一号三维成像.pdf",
     "http://scis.scichina.com/en/2025/177301.pdf"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        ctype = r.headers.get("Content-Type", "")
        buf = bytearray()
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > CAP:
                raise RuntimeError("exceeds 30 MB")
    return bytes(buf), ctype


def main():
    only = set(sys.argv[1:])
    log = json.loads(LOGF.read_text(encoding="utf-8")) if LOGF.exists() else {}
    for lid, name, url in ITEMS:
        if only and lid not in only:
            continue
        if lid in log and log[lid].get("ok"):
            continue
        try:
            data, ctype = get(url)
            if not data.startswith(b"%PDF"):
                raise RuntimeError(f"not a PDF (Content-Type={ctype}, {len(data)} B)")
            path = DOC / name
            path.write_bytes(data)
            with fitz.open(path) as pdf:
                text = "\n".join(p.get_text() for p in pdf)
                pages = pdf.page_count
            (TXT / (lid + ".txt")).write_text(text, encoding="utf-8")
            log[lid] = {"ok": True, "file": name, "url": url, "bytes": len(data), "pages": pages}
            print("ok", lid, len(data), pages, flush=True)
        except Exception as e:  # noqa: BLE001
            log[lid] = {"ok": False, "file": name, "url": url, "err": str(e)[:200]}
            print("FAIL", lid, e, flush=True)
        LOGF.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
