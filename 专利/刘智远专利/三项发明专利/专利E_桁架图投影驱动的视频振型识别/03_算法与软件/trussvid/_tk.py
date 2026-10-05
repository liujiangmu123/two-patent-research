# -*- coding: utf-8 -*-
"""定位共享库 towerkit（ROOT/00_共享/towerkit），也可通过环境变量 TOWERKIT_PATH 指定其父目录。"""
import os
import sys
from pathlib import Path


def _find():
    env = os.environ.get("TOWERKIT_PATH")
    if env and (Path(env) / "towerkit").is_dir():
        return Path(env)
    p = Path(__file__).resolve()
    for parent in p.parents:
        cand = parent / "00_共享"
        if (cand / "towerkit").is_dir():
            return cand
    raise ImportError("未找到共享库 towerkit，请设置环境变量 TOWERKIT_PATH 为 00_共享 目录")


_path = str(_find())
if _path not in sys.path:
    sys.path.insert(0, _path)

import towerkit  # noqa: E402,F401
