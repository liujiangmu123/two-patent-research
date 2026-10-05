# -*- coding: utf-8 -*-
"""anglegs：桁架图参数化角钢高斯泼溅与激光雷达联合反演（专利A 算法实现，纯 numpy/autograd，CPU）。

模块：
  params     桁架图参数（节点、肢宽 b、肢朝向 phi、偏心 delta、存在 logit）与打包/解包
  primitives 确定性生成函数：杆件 -> 角钢两肢面元高斯条带（离散面元与连续极限）
  render     同一高斯场的影像（轮廓/光度）与激光（期望距离/回波概率，足迹协方差叠加）渲染
  synth      合成观测：真值塔几何 -> 相机像素射线、激光束（子光线足迹）、植被遮挡
  optimize   联合损失与 L-BFGS 优化（梯度只回传节点与截面参数），对称软先验、外参/时间偏移
  topology   面板语法候选、存在概率剪枝与零能模态检查
  confidence 拉普拉斯/Fisher 对角近似置信度与校准
  nbv        置信度 x 有限元灵敏度补测视点规划（带电安全壳约束）
  baseline   PTM 式 LiDAR-only 点到中心线图优化基线
  metrics    RMSEn/NGED/肢宽/规格/朝向/AUC/ECE/FE 误差
  change     多期变化检测
"""
__version__ = "0.1.0"
