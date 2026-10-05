# -*- coding: utf-8 -*-
"""R2 patent scan v2: incremental save, >=7 s spacing, abort on first 503 (temporary helper)."""
import json
import sys
import time
import urllib.error
from pathlib import Path

TOOL = Path(r"h:\Axinjihua\02动画项目\05动画Harness工作台\专利文档资料\专利\刘智远专利\三项发明专利\00_共享\工具")
sys.path.insert(0, str(TOOL))
sys.stdout.reconfigure(encoding="utf-8")
from patent_search import query  # noqa: E402
from patent_detail import fetch  # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "_R2_patent_raw.json"
LOG = BASE / "_R2_request_log.txt"


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    print(msg, flush=True)


def main():
    mode = sys.argv[1]
    items = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for it in items:
        key = it["q"] if mode == "search" else it["no"]
        try:
            if mode == "search":
                total, rows = query(it["q"], it.get("after", "20190101"), it.get("num", 20))
                res[key] = {"total": total, "rows": rows}
                log(f"search ok {total} | {key}")
            else:
                res["detail:" + key] = fetch(key)
                log(f"detail ok | {key} | {res['detail:' + key]['title'][:40]}")
        except urllib.error.HTTPError as e:
            log(f"HTTP {e.code} | {key}")
            if e.code == 503:
                OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
                log("abort on 503")
                return
        except Exception as e:  # noqa: BLE001
            log(f"ERR {e} | {key}")
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(7)
    log("done")


if __name__ == "__main__":
    main()
