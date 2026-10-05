# -*- coding: utf-8 -*-
"""Second-round targeted prior-art queries (abstract snippets via the Google Patents query endpoint)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patent_search import query  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "patent_hits2.md"
QUERIES = [
    ("铁塔 PS 像元 仿真 差分干涉 三维点云", "20200101"),
    ("输电塔 角反射器 InSAR 温度 热膨胀", "20180101"),
    ("输电塔 InSAR 有限元 基础 不均匀沉降 应力", "20180101"),
    ("杆塔 点云 节点 拓扑图 连接 概率 分段", "20200101"),
    ("杆塔 点云 投影 一维 峰值 检测 节点", "20200101"),
    ("铁塔 点云 截面 肢宽 肢厚 有限元", "20200101"),
    ("铁塔 点云 模型 修正 模态 频率 更新", "20200101"),
    ("铁塔 点云 置信度 杆件 可靠性", "20200101"),
    ("冻土 输电塔 基础 冻胀 InSAR", "20180101"),
    ("光伏 支架 点云 桁架 有限元", "20200101"),
    ("定日镜 支架 形变 点云 有限元", "20200101"),
    ("风电 塔架 点云 有限元 模型 生成", "20200101"),
    ("通信塔 点云 杆件 重建 有限元", "20200101"),
    ("输电塔 点云 螺栓 滑移 刚度 修正", "20200101"),
]


def main():
    lines = ["# 第二轮定向查新\n"]
    for q, after in QUERIES:
        try:
            total, rows = query(q, after, num=15)
        except Exception as e:
            lines.append(f"\n## {q}\n查询失败：{e}\n")
            print("FAIL", q, e)
            time.sleep(5)
            continue
        lines.append(f"\n## {q}（优先权≥{after}，命中 {total}）\n")
        for r in rows[:12]:
            lines.append(f"- {r['no']} | {r['prio']} | {r['assignee']} | {r['title']}\n  - {r['snippet']}")
        print(f"{total:>5}  {q}")
        time.sleep(2.5)
    OUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
