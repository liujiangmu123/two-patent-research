# fiminsar

杆件级桁架有限元影响矩阵作 InSAR 视线向观测算子，解耦热胀/风/基础位移，反演各塔腿基础差异沉降与倾斜（专利C）。依赖共享库 `ROOT/00_共享/towerkit`（自动定位，或设 `TOWERKIT_PATH` 为其父目录），未修改 towerkit。

环境：Python 3.14，numpy、scipy、matplotlib、pytest（项目 `.venv`）。

```
cd 03_算法与软件
python -m fiminsar.cli influence                 # 影响矩阵与塔顶影响系数
python -m fiminsar.cli demo --epochs 12 --legs -10 -2 -1 -2 --out out.json
python -m fiminsar.cli dopt -m 4                 # D 最优角反射器布设
python -m pytest -q tests                        # 7 项测试
python examples/example_demo.py
```

## 模块—权利要求特征对应表

| 步骤/特征（交底书） | 模块与函数 |
|---|---|
| S1 杆件级桁架有限元模型，塔腿支座节点 | `model.build_model`（towerkit `build_tower` + `FEModel.fix_base`） |
| S2 基础位移单位工况影响矩阵 G_b（每腿 x/y/z 共 12 列） | `model.build_model` → `TowerModel.Gb`（`FEModel.influence_matrix` 支座强制位移） |
| S2 热基列 G_T（ψ1 均匀温升、ψ2 日照分布）、风列 G_w | `TowerModel.GT1`、`TowerModel.thermal_column`、`TowerModel.Gw` |
| S3 太阳位置、角钢两肢法向、桁架射线投射遮挡比例 η、杆件温升 | `thermal.sun_vector / irradiance / angle_leg_normals / shadow_fraction / solar_term` |
| S4 候选散射体（塔顶、横担端、塔腿角钢二面角、夹持式 CR）、可见性 | `scatter.candidates / visible / select_ps` |
| S4 PS–杆件节点概率关联 p_kc 与阈值 p0 | `scatter.associate` |
| S5 视线向观测算子 H = L P G；CR 相位中心偏置 u_q+θ_q×ρ | `scatter.Geometry.los`、`TowerModel.point_rows`、`sim.synthesize` 中组装 |
| S6 升降轨联合时序正则化最小二乘（参考景差分、二阶平滑、τ/风先验、水平分量约束）、后验协方差 | `invert.invert`、`invert.Options` |
| S7 基础倾斜、塔顶倾斜正演、上置信界分级预警 | `invert.foundation_tilt / top_tilt / warning_level` |
| S8 Fisher 信息 D 最优反射器贪心布设 | `invert.d_optimal`、`cli dopt` |
| 对比方法（经验热胀阈值+单点、刚体倾斜模型） | `sim.method_empirical / method_rigid` |

说明：复成一号式几何（入射 35°/38°、过境 10:30/14:30、重访 11 d）为仿真假设参数，非官方轨道参数；Sentinel-1 取 towerkit `SATS`。
