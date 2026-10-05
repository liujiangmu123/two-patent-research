# towercal：规范逆向设计 + 环境振动贝叶斯标定（专利B 算法与软件）

依赖：Python ≥3.10、numpy、scipy（matplotlib 仅绘图用）、共享库 `../../00_共享/towerkit`（导入 `towercal` 时自动加入路径）。
测试：`python -m pytest -q tests`（12 项，约 8 s）。示例：`python examples/demo_small_tower.py`（约 1 min）。

## 命令行

```
python -m towercal.cli extract   --tower suspension --ins 5.2          # 设计输入提取
python -m towercal.cli prior     --tower suspension --ins 5.2 --out prior.json
python -m towercal.cli sensors   --tower suspension --ins 5.2 --n 8    # EfI 测点 vs 经验布置
python -m towercal.cli demo      --tower small --ins 2.5 --out demo.json
python -m towercal.cli calibrate --graph g.json --acc acc.npy --fs 20 --nodes 9,15,186,... --out post.json
```
`--graph` 读入 towerkit TrussGraph JSON。这个模型可以来自任何测量手段（激光点云、影像或台账），只需要节点、杆件类别/部位/分组和导地线挂点。`--acc` 是 (nt, 3×测点数) 加速度数组。

## 模块与权利要求特征对应表

| 权利要求特征（拟） | 模块 / 函数 | 说明 |
|---|---|---|
| S1 由杆件级桁架模型自动提取设计输入：呼高、全高、根开、横担长、导地线挂点数、回路数 | `extract.extract_design_input` | 用挂点高程聚类得到横担层，用挂点水平距离得到横担长 |
| S1a 绝缘子串长 → 电压等级（规则表 + 相间距一致性校核 + 置信度） | `extract.VOLTAGE_TABLE`, `_voltage_from_insulator` | 置信度决定先验情景里电压等级的混合权重 |
| S1b 转角 → 塔型；相邻塔位 → 水平/垂直档距 | `extract_design_input(neighbor_xy=…)` | 无相邻塔位时，按串型或根开/全高比判塔型，转角取规则缺省 |
| S2 DL/T 5486 荷载组合（大风 0/45/90°、覆冰、断线；γG=1.2、γQ=1.4；风振系数） | `design.load_cases`, `wire_loads` | 塔身风荷载复用 towerkit.loads.wind_static |
| S2a GB 50017 稳定（b 类 φ）、单肢连接折减、长细比限值、最小规格 | `design.member_capacity`, `lam_limit`, `MIN_SECTION` | |
| S2b 按对称与面板分组的离散截面优化（分组满应力 + 角钢目录最轻可行档） | `design.size_groups`, `reverse_design` | 优化器可替换（ISSA、GA 等） |
| S3 规范逆向设计截面先验：不可观测输入（风速、档距、覆冰、设计裕度、电压等级、转角）情景采样 → 每情景逆向设计 → 离散分布 | `design.sample_scenarios`, `build_prior` | 先验同时输出边缘 pmf 和情景集合 |
| S3a 设计一致性混合先验（保留组间相关）+ 档位偏差核（施工替代） | `bayes.MixturePrior` | 是本发明区别于逐组独立先验的地方 |
| S4 参数化有限元：截面组 (A, I, J) 线性分解、连接刚度折减 κ、基础平动弹簧 k_v | `model.ParamTower` | |
| S4a 多锚点 Ritz 基模态降阶代理（r≈67，单次特征分析 <1 ms，频率误差 ≤1.4%） | `model.ReducedModel` | |
| S5 Fisher 信息 / 有效独立法三轴节点测点优化（候选：主材角点、横担端、地线支架端） | `sensors.efi_nodes`, `select_dopt` | 经验布置对照：`empirical_nodes` |
| S6 环境振动 OMA：SSI-COV + 稳定图 + 聚类 + MPC 筛选 | `oma.*`, `pipeline.identify` | |
| S6a 测量误差模型：MEMS 噪声谱、温漂、GNSS 授时同步误差 | `excitation.MemsNoise` | 仿真用 |
| S7 贝叶斯修正：TMCMC，似然 = 频率 + MAC（门限配对），后验为截面组离散分布 + κ、k_v 连续分布 | `bayes.ModalLikelihood`, `tmcmc`, `posterior_sections` | |
| S8 标定模型的设计风荷载验算：塔顶位移、杆件应力比、超限杆件 | `check.design_response`, `verdict` | |
| 对照：PTM 统一截面 / 常规缩放修正 / 逐组均匀先验 | `04_仿真验证/脚本/run_sim.py` | |

## 限制

- 规范荷载为简化口径：导线风荷载、风振系数取常数，未做按 DL/T 5551 的逐段体型系数。结果用于方法对比，不能替代设计院计算。
- 截面观测通道只作为接口保留：`ParamTower.group_props` 可接收任何来源的截面观测并据此缩窄先验。本包不包含具体的截面测量算法。
