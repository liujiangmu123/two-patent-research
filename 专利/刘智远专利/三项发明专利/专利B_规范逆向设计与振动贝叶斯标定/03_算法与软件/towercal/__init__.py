# -*- coding: utf-8 -*-
"""towercal：基于杆件级桁架模型规范逆向设计与环境振动贝叶斯标定的输电塔截面反演（专利B 算法包）。

模块
- extract   由桁架模型自动提取设计输入（呼高、横担长、挂点数、绝缘子串长→电压等级、转角→塔型、档距）
- design    DL/T 5486 / GB 50017 荷载组合与稳定、长细比约束下的分组离散截面优化；规范逆向设计截面先验
- model     参数化有限元（截面组刚度系数、连接刚度折减、基础柔度）与 Ritz 模态降阶代理
- sensors   Fisher 信息 / 有效独立法测点优化与经验布置
- excitation 脉动风环境激励模态时程与 MEMS 测量误差（噪声谱、温漂、同步误差）
- oma       协方差驱动随机子空间（SSI-COV）运行模态识别
- bayes     TMCMC 贝叶斯模型修正与截面组离散后验
- check     设计风荷载下位移、应力比验算与评价指标
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "00_共享"))
if os.path.isdir(_SHARED) and _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

__version__ = "1.0.0"
