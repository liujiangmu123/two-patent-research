# -*- coding: utf-8 -*-
"""livenbv：杆件置信度驱动、带电安全壳约束的输电塔无人机补测航线规划（专利D）。

模块：
  scenario     合成塔真值/设计先验、变体（高低腿/缺材/遮挡）、带电导线几何、初始双倾角航线
  safety       DL/T 409 最小安全距离 + 定位误差裕度 → 带电安全壳；点/航段违规检测
  confidence   杆件级观测累积、三态对称判别、几何置信度、节点估计、缺材确认
  sensitivity  有限元灵敏度（塔顶位移伴随法 + 模态频率）→ 结构重要性权重
  viewpoints   安全壳外候选视点生成与期望观测预测
  planner      结构重要性加权信息增益（子模）贪心选点、安全图最短路 + TSP 航线、停止判据
  evaluate     指标：覆盖率、低置信杆件数、节点 RMSE、FE 塔顶位移/频率误差、违规次数
  pipeline     四种方法（无补测/均匀环绕/纯几何 NBV/本发明）的端到端仿真
"""
from . import _tk  # noqa: F401
from .safety import SafetyShell, min_distance_dlt409  # noqa: F401

__version__ = "1.0.0"
