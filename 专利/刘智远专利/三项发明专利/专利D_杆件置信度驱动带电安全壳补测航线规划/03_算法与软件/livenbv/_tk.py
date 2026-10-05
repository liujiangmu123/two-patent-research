# -*- coding: utf-8 -*-
"""定位并导入共享库 towerkit（ROOT/00_共享/towerkit）。"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
_shared = os.path.join(_root, "00_共享")
if os.path.isdir(_shared) and _shared not in sys.path:
    sys.path.insert(0, _shared)

import towerkit as tk  # noqa: E402,F401
from towerkit import fem, graph, lidar, loads, tower  # noqa: E402,F401
