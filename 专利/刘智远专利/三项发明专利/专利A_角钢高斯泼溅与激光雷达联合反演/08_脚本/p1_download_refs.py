# -*- coding: utf-8 -*-
"""下载专利1 调研用开放获取文献/规格书 PDF（单个文件 < 30 MB；失败记录链接）。

输出：01_调研与查新/文献/*.pdf 与 文献/_下载记录.json
运行：.venv\\Scripts\\python.exe <本文件> [仅下载的文件名前缀...]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
P1 = Path(__file__).resolve().parent.parent
DST = P1 / "01_调研与查新" / "文献"
DST.mkdir(parents=True, exist_ok=True)
LOG = DST / "_下载记录.json"
MAX_BYTES = 30 * 1024 * 1024

REFS = [
    ("R01_Lamas2023_桁架桥点云实例语义分割.pdf", "https://www.investigo.biblioteca.uvigo.es/xmlui/bitstream/11093/4752/4/2023_lamas_point_clouds.pdf"),
    ("R02_Lamas2023_桁架桥合成点云.pdf", "https://www.investigo.biblioteca.uvigo.es/xmlui/bitstream/11093/5438/1/2023_lamas_point_clouds.pdf"),
    ("R03_Qiao2022_构件分割与模型匹配塔重建.pdf", "https://www.mdpi.com/2072-4292/14/19/4905/pdf"),
    ("R04_Zhou2017_启发式塔重建.pdf", "https://www.mdpi.com/2072-4292/9/11/1172/pdf"),
    ("R05_Chen2019_抽象模板塔重建.pdf", "https://www.mdpi.com/2072-4292/11/13/1579/pdf"),
    ("R06_SymmCompletion2025_对称引导补全.pdf", "https://arxiv.org/pdf/2503.18007"),
    ("R07_QualityGuidedNBV2025_质量引导无人机NBV.pdf", "https://arxiv.org/pdf/2511.20353"),
    ("R08_FU-MPC2026_电机旋转激光雷达无人机探索.pdf", "https://arxiv.org/pdf/2605.14920"),
    ("R09_FC-Planner2023_骨架引导覆盖规划.pdf", "https://arxiv.org/pdf/2309.13882"),
    ("R10_Roberts2017_子模航迹优化.pdf", "https://arxiv.org/pdf/1705.00703"),
    ("R11_Review2022_无人机重建视点与路径规划综述.pdf", "https://arxiv.org/pdf/2205.03716"),
    ("R12_HELIOS++2021_虚拟激光扫描.pdf", "https://arxiv.org/pdf/2101.09154"),
    ("R13_QualityAdaptiveMultiUAV2026.pdf", "https://arxiv.org/pdf/2607.24233"),
    ("R14_Huang2022_无人机激光塔倾斜评估.pdf", "https://www.mdpi.com/2072-4292/14/2/408/pdf"),
    ("R15_Zhou2026_格构钢塔倾斜检测截面算法.pdf", "https://www.mdpi.com/1424-8220/26/17/5558/pdf"),
    ("R16_Skeleton2026_骨架螺旋覆盖路径.pdf", "https://www.mdpi.com/2076-3417/16/17/8743/pdf"),
    ("R17_ShapePrior2026_无人机激光塔提取.pdf", "https://www.mdpi.com/2072-4292/18/13/2082/pdf"),
    ("R18_TUM_钢框架点云重建.pdf", "https://mediatum.ub.tum.de/doc/1785448/1785448.pdf"),
    ("S01_RIEGL_VUX-120-23_规格书.pdf", "https://www.thefuture3d.com/spec-sheets/riegl/RIEGL_VUX-120-23__Datasheet_2026-08-20_EN.pdf"),
    ("S02_RIEGL_miniVUX-3UAV_规格书.pdf", "https://ggs-solutions.eu/wp-content/uploads/2024/05/miniVUX-3UAV-Data-Sheet.pdf"),
    ("S03_Hesai_XT32M2X_折页.pdf", "https://3fcd7a14-6521-4f80-9edc-873fa9919932.filesusr.com/ugd/42e3eb_87f17fd6b5154513970ba9a42d3cf759.pdf"),
    ("T01_DLT409-2023_电力安全工作规程线路部分_报批稿.pdf", "https://hbba.sacinfo.org.cn/portal/download/00913ed979aad12bc2c4621e047a6b2d265a2cc9437d6f7fa118188c84afd486"),
    ("T99_hbba_e8b44_待识别.pdf", "https://hbba.sacinfo.org.cn/portal/download/e8b44e4dce0945ff401d206e245aa2df5ca6149b88772a4d3979277565ef3e22"),
]


try:
    import certifi
    import ssl
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # 无 certifi 时退回系统证书
    CTX = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        data = r.read(MAX_BYTES + 1)
        ctype = r.headers.get("Content-Type", "")
    if len(data) > MAX_BYTES:
        raise ValueError("超过 30 MB，放弃")
    if not data[:5].startswith(b"%PDF"):
        raise ValueError(f"非 PDF（{ctype}）")
    return data


def main():
    only = sys.argv[1:]
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    for name, url in REFS:
        if only and not any(name.startswith(o) for o in only):
            continue
        out = DST / name
        if out.exists() and out.stat().st_size > 0:
            log[name] = {"url": url, "ok": True, "bytes": out.stat().st_size}
            continue
        try:
            data = fetch(url)
            out.write_bytes(data)
            log[name] = {"url": url, "ok": True, "bytes": len(data)}
            print("ok  ", name, len(data) // 1024, "KB", flush=True)
        except Exception as e:
            log[name] = {"url": url, "ok": False, "error": str(e)}
            print("FAIL", name, e, flush=True)
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
