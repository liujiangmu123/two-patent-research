# -*- coding: utf-8 -*-
"""示例：small 合成塔（32 m）端到端——提取设计输入 → 逆向设计先验 → EfI 测点 → 合成环境振动 → SSI-COV → TMCMC。
运行：python examples/demo_small_tower.py（约 1 分钟）
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
from towercal import cli  # noqa: E402

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "demo_small_result.json")
    cli.main(["demo", "--tower", "small", "--ins", "2.5", "--n", "6", "--scen", "8", "--samples", "300",
              "--out", out])
    print(open(out, encoding="utf-8").read())
