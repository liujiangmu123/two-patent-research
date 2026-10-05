# -*- coding: utf-8 -*-
"""示例：直线塔、复成一号式升降轨各 12 景，腿1 沉降 10 mm，反演并输出预警（结果写 example_out.json）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fiminsar.cli import main  # noqa: E402

main(["demo", "--epochs", "12", "--legs", "-10", "-2", "-1", "-2",
      "--out", str(Path(__file__).with_name("example_out.json"))])
main(["dopt", "-m", "4"])
