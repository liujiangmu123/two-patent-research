# -*- coding: utf-8 -*-
"""专利3 查新检索（Google Patents 公共查询接口，仅发送关键词）。

限速纪律：每次请求间隔 >= 6 s；遇 503 暂停 90 s 再试一次；全部请求（检索 + 详情）累计 <= 40 次，
计数持久化在 _req_counter.json，跨多次运行累加。

用法：
  .venv\\Scripts\\python.exe <本文件> search            # 跑检索式
  .venv\\Scripts\\python.exe <本文件> detail CN1 CN2 ...  # 取详情（摘要 + 权利要求）
"""
import json
import sys
import time
import urllib.error
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2] / "00_共享" / "工具"
sys.path.insert(0, str(TOOLS))
from patent_search import query  # noqa: E402
import html  # noqa: E402
import re  # noqa: E402
import urllib.request  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def fetch(no):
    """与 00_共享/工具/patent_detail.fetch 相同的解析逻辑，但保留更长的权利要求文本与申请人/日期。"""
    url = f"https://patents.google.com/patent/{no}/zh"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        page = r.read().decode("utf-8", "ignore")
    g = lambda pat: (lambda m: html.unescape(m.group(1)).strip() if m else "")(re.search(pat, page, re.S))
    claims = re.search(r'<section itemprop="claims".*?</section>', page, re.S)
    ctext = ""
    if claims:
        ctext = re.sub(r"<[^>]+>", " ", claims.group(0))
        ctext = re.sub(r"\s+", " ", html.unescape(ctext)).strip()
    return {
        "title": g(r'<meta name="DC.title" content="([^"]*)"'),
        "abstract": g(r'<meta name="DC.description" content="([^"]*)"'),
        "claims": ctext[:6000],
        "status": g(r'itemprop="legalStatusIfi"[^>]*>\s*([^<]+)<'),
        "assignee": g(r'<meta name="DC.contributor" content="([^"]*)" scheme="assignee"'),
        "prio": g(r'<time itemprop="priorityDate"[^>]*>([^<]+)<'),
        "pubdate": g(r'<meta name="DC.date" content="([^"]*)"'),
    }
COUNTER = HERE / "_req_counter.json"
MAX_REQ = 40
GAP = 6.5

QUERIES = [
    # (编号, 检索式, 优先权起始)
    ("Q01", "铁塔 截面 规格 反演 点云", "20150101"),
    ("Q02", "杆塔 角钢 规格 识别 激光 点云 有限元", "20150101"),
    ("Q03", "输电塔 截面 识别 振动 模态", "20150101"),
    ("Q04", "输电塔 模态 有限元 模型修正", "20150101"),
    ("Q05", "铁塔 环境激励 模态参数 识别 随机子空间", "20150101"),
    ("Q06", "输电塔 贝叶斯 模型修正", "20150101"),
    ("Q07", "输电塔 数字孪生 有限元 点云 模态", "20180101"),
    ("Q08", "角钢 振动传感器 夹持 铁塔", "20150101"),
    ("Q09", "角钢 传感器 安装 夹具 免打孔 输电塔", "20150101"),
    ("Q10", "输电塔 优化设计 截面 规范 角钢 规格", "20150101"),
    ("Q11", "铁塔 杆件 选材 优化 离散 遗传算法 塔重", "20150101"),
    ("Q12", "输电塔 螺栓 滑移 节点刚度 模态", "20150101"),
    ("Q13", "输电塔 传感器 优化布置 模态 信息熵", "20150101"),
    ("Q14", "输电塔 振动 监测 无线 节点 GNSS 授时 同步", "20150101"),
    ("Q15", "点云 绝缘子串 长度 电压等级 杆塔 识别", "20150101"),
    ("Q16", "点云 导线 档距 挂点 杆塔 荷载 计算", "20150101"),
    ("Q17", "老旧 铁塔 设计参数 反推 承载力 评估", "20150101"),
    ("Q18", "有限元模型修正 离散参数 截面 规格 贝叶斯", "20150101"),
    ("Q19", '"transmission tower" "model updating" (Bayesian OR modal)', "20150101"),
    ("Q20", '("lattice tower" OR "transmission tower") "operational modal analysis"', "20150101"),
    ("Q21", '"tower" "cross-section" identification "ambient vibration" "finite element"', "20150101"),
    ("Q22", '"transmission tower" "digital twin" "point cloud" "finite element"', "20180101"),
    ("Q23", '"angle" "lattice tower" accelerometer clamp wireless', "20150101"),
    ("Q24", '"structure" "Bayesian model updating" "discrete" section catalog', "20150101"),
]


def _load_counter():
    if COUNTER.exists():
        return json.loads(COUNTER.read_text(encoding="utf-8"))
    return {"count": 0, "log": []}


def _save_counter(c):
    COUNTER.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def _guarded(fn, tag, *args):
    """执行一次请求；503 则暂停 90 s 再试一次。每次请求都计数。"""
    c = _load_counter()
    for attempt in (1, 2):
        if c["count"] >= MAX_REQ:
            raise RuntimeError("已达 40 次请求上限，停止")
        c["count"] += 1
        c["log"].append({"tag": tag, "attempt": attempt, "t": time.strftime("%Y-%m-%d %H:%M:%S")})
        _save_counter(c)
        try:
            out = fn(*args)
            time.sleep(GAP)
            return out
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt == 1:
                print(f"  503 on {tag}, sleep 90 s")
                time.sleep(90)
                continue
            time.sleep(GAP)
            raise
        except Exception:
            time.sleep(GAP)
            raise
    return None


def run_search():
    out_path = HERE / "search_raw.json"
    res = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for qid, q, after in QUERIES:
        if qid in res and "rows" in res[qid]:
            continue
        try:
            total, rows = _guarded(query, qid, q, after, 30)
            res[qid] = {"q": q, "after": after, "date": date.today().isoformat(), "total": total, "rows": rows}
            print(f"{qid} {total!s:>6} {q}")
        except Exception as e:  # 记录失败；503 连续失败则整体停止以节省请求额度
            res[qid] = {"q": q, "after": after, "date": date.today().isoformat(), "error": str(e)}
            print(f"{qid} FAIL {e}")
            out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            if "上限" in str(e) or "503" in str(e):
                print("stop: service unavailable / quota")
                break
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def run_detail(nums):
    out_path = HERE / "detail_raw.json"
    res = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for no in nums:
        if no in res and "abstract" in res[no]:
            continue
        try:
            d = _guarded(fetch, "D:" + no, no)
            res[no] = d
            print("ok", no, d["title"][:50], d["status"])
        except Exception as e:
            res[no] = {"error": str(e)}
            print("FAIL", no, e)
            out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            if "上限" in str(e) or "503" in str(e):
                print("stop: service unavailable / quota")
                break
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "detail":
        run_detail(sys.argv[2:])
    else:
        run_search()
    print("requests used:", _load_counter()["count"])
