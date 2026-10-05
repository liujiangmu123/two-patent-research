# -*- coding: utf-8 -*-
"""单次探针（不重试），计入请求计数，用于判断 Google Patents 是否恢复。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_search as R  # noqa: E402

c = R._load_counter()
c["count"] += 1
c["log"].append({"tag": "probe:Q02", "attempt": 1, "t": time.strftime("%Y-%m-%d %H:%M:%S")})
R._save_counter(c)
try:
    total, rows = R.query(R.QUERIES[1][1], R.QUERIES[1][2], 30)
    print("OK", total, len(rows))
    import json
    from datetime import date
    p = R.HERE / "search_raw.json"
    res = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    res["Q02"] = {"q": R.QUERIES[1][1], "after": R.QUERIES[1][2], "date": date.today().isoformat(), "total": total, "rows": rows}
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
except Exception as e:
    print("FAIL", e)
print("count", c["count"])
