# -*- coding: utf-8 -*-
"""定位共享库 towerkit（ROOT/00_共享/towerkit），可用环境变量 TOWERKIT_PARENT 覆盖。"""
import os
import sys
from pathlib import Path


def ensure_towerkit():
    env = os.environ.get("TOWERKIT_PARENT")
    cands = [Path(env)] if env else []
    here = Path(__file__).resolve()
    for p in here.parents:
        cands.append(p / "00_共享")
    for c in cands:
        if (c / "towerkit" / "__init__.py").exists():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            return c
    raise ImportError("未找到 towerkit，请设置环境变量 TOWERKIT_PARENT 指向 00_共享 目录")


ensure_towerkit()
