# livenbv：杆件置信度驱动的带电安全壳补测航线规划（专利D）

依赖：Python 3.14、numpy、scipy、matplotlib、numba，以及共享库 `ROOT/00_共享/towerkit`（自动加入路径，未作修改）。

```
python -m livenbv.cli shell --kv 500 --sigma 0.5          # 安全壳半径构成
python -m livenbv.cli run --variant combined --method all  # 四方法对比
python -m pytest -q tests                                  # 9 项单元测试
python examples/example_combined.py
```

## 模块与权利要求特征对应

| 权利要求特征 | 模块/函数 |
|---|---|
| 初始常规航线（双倾角扫描）采集点云 | `scenario.initial_flight`，`pipeline.Context._initial_evidence` |
| 点云 → 杆件归属、杆轴拟合、节点最小二乘交会 | `confidence.assign_points / fit_lines / intersect_nodes` |
| 杆件几何置信度：点数项 q_n、视角覆盖项 q_v（绕杆轴 6 扇区） | `confidence.compute_confidence`，`confidence.view_bins` |
| 对称一致性三态判别（一致/冲突/不可判），剔除整体倾斜趋势；对称借用 | `confidence.compute_confidence`，`scenario.mirror_maps` |
| 杆件存在性（实测/期望点数比，负证据） | `confidence.compute_confidence`（exist） |
| 有限元灵敏度：塔顶位移伴随法 + 模态频率灵敏度 → 结构重要性权重 | `sensitivity.sensitivities / importance_weights` |
| 按电压等级的 DL/T 409 最小距离 + kσ 定位误差 + 漂移 + 机体半径 → 带电安全壳 | `safety.min_distance_dlt409`，`safety.SafetyShell` |
| 安全壳与结构避碰区外的候选视点生成，以及期望观测预测 | `viewpoints.generate / aim / predict` |
| 结构重要性加权信息增益（子模），按代价归一的懒惰贪心 | `planner.predicted_cgeo / objective / lazy_greedy` |
| 安全可行图（整段在壳外的边）+ 最短路度量闭包 + TSP（最近邻 + 2-opt） | `planner.safe_graph / tsp_route / expand_route` |
| 增量评估：每轮飞行后更新置信度，用实测/预测增益比修正预测模型 | `pipeline.run_nbv`（hit_frac） |
| 停止判据（缺口阈值 / 边际增益率 / 增益比 / 预算） | `planner.StopRule` |
| 航迹违规审计 | `safety.SafetyShell.violations` |
| 评价指标 | `evaluate.metrics` |

仿真脚本与报告见 `../04_仿真验证/`。
