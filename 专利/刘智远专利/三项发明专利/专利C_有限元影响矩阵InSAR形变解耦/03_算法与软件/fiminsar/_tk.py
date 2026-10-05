# -*- coding: utf-8 -*-
"""定位并导入共享库 towerkit（ROOT/00_共享/towerkit），也可用环境变量 TOWERKIT_PATH 指定其父目录。"""
import os
import sys
from pathlib import Path

_cands = [os.environ.get("TOWERKIT_PATH", ""), str(Path(__file__).resolve().parents[3] / "00_共享")]
for _c in _cands:
    if _c and (Path(_c) / "towerkit" / "__init__.py").exists():
        if _c not in sys.path:
            sys.path.insert(0, _c)
        break

import towerkit  # noqa: E402,F401
from towerkit import fem, loads, sar, build_tower  # noqa: E402,F401
from towerkit.graph import point_segment_distance  # noqa: E402,F401
