# TrussTwin 工程核心原型

这是可运行的 CPU 几何拟合、离散厚度候选、条件性承载筛查和补测选择原型。它没有从原始照片自动完成全流程重建，没有进行实景 3DGS 训练，也不是工程规范合规证书。

## 从项目根运行

一律使用项目根 `.venv\Scripts\python.exe`，当前环境已有 numpy、scipy、pytest，未新增或安装依赖。

```powershell
.\.venv\Scripts\python.exe '专利\刘智远专利\工程实现_20261003\software\trusstwin\cli.py' --demo --out '专利\刘智远专利\工程实现_20261003\software\trusstwin\output_demo'
.\.venv\Scripts\python.exe '专利\刘智远专利\工程实现_20261003\software\trusstwin\cli.py' --demo --with-thickness --out '专利\刘智远专利\工程实现_20261003\software\trusstwin\output_measured'
.\.venv\Scripts\python.exe '专利\刘智远专利\工程实现_20261003\software\trusstwin\cli.py' --case '你的案例.json' --out '输出目录'
.\.venv\Scripts\python.exe -m pytest '专利\刘智远专利\工程实现_20261003\software\tests' -q
```

CLI 验证失败时退出码为 2，并向 stderr 输出 JSON 错误信息。`--case` 使用 UTF-8/UTF-8 BOM JSON。

## Python API

将本目录加入 Python 模块路径后：

```python
from trusstwin.pipeline import run_case, demo_case

case = demo_case()
result = run_case(case, output_dir=None)  # 无输出目录时只返回字典
case['measurements'].append({
    'kind': 'thickness', 'member_id': 'M1',
    'value_m': 0.010, 'sigma_m': 0.00015
})
updated = run_case(case)
```

`run_case` 会深拷贝输入，禁止测量值为负、厚度不在 `(0,width)`、非正噪声、缺少材料或隐含单位。全局单位字段必须是 `"units":"m-N-Pa"`，没有自动猜测毫米、千牛或兆帕。

## 案例结构

- `nodes`：`{"节点ID":[x,y,z]}`，多个杆件通过同一 ID 共享节点。节点坐标当前固定。
- `members`：每项含 `id`、`nodes:[start_id,end_id]`、`width_m`、`thickness_candidates_m`；可提供 `orientation_rad`、`candidate_priors`、`effective_length_factor` 和 `exists:false`。杆件线是截面形心线。只有一个截面候选且没有有效测厚时，不能因此称为测量已证实；固定输入的来源应显式为 `section_source:"verified_as_built"` 或合成演示的 `"synthetic_known_input"`，其他单候选状态为 `unverified_single_section_input`。
- `material`：显式 `E_Pa` 与 `yield_strength_Pa`；不从照片猜钢号。
- `supports`：`[{"node":"节点ID","dofs":[0,1,2]}]`，自由度 0/1/2 对应全局 x/y/z。
- `loads`：`[{"node":"节点ID","force_N":[Fx,Fy,Fz]}]`。所有给定荷载组合当前作为一次线性静力工况，荷载可靠性由输入方负责。
- `measurements`：人工关联至杆件的有效观测。下面列出实际实现的接口。
- `planned_actions`：可选候选测量模板，带 `kind`、`member_id`、噪声、相机/扫描方向及 `cost_units`。未提供时生成遥测影像、激光和现场测厚三种演示模板；相对成本单位是算法输入，不是实际报价。

每个离散厚度内部可开启真实连续几何拟合：

```json
"fit": {
  "width": true,
  "orientation": true,
  "width_bounds_m": [0.080, 0.120],
  "orientation_bounds_rad": [-0.4, 0.4]
}
```

使用 `scipy.optimize.least_squares` 对白化的真实几何残差优化肢宽和截面朝向，输出优化状态、雅可比奇异值和局部秩。离散厚度保留为独立候选。`posterior` 来自给定先验和 profile Gaussian likelihood，`likelihood_only_weights` 单独显示观测支持。候选保留和补测使用后者，极强先验不能把观测等价候选强制消除。未对连续参数积分，也未做实测 coverage 校准。

## 已实现的联合观测

1. `lidar_points`：`points_m` 是非空 Nx3 全球坐标数组，含 `sigma_m`，可提供 `beam_diameter_m`。残差是点到有限厚度角钢三角表面的最近距离。噪声近似为 `sqrt(sigma_m²+beam_diameter_m²/12)`。这只是束足迹不确定度近似，不能称为完整激光物理返回渲染。
2. `image_points`：`pixels` 是 Nx2；`feature` 为 `section_vertices` 或 `endpoints`，`indices` 选择已人工关联的六个截面顶点或两个共享节点端点。使用完整针孔投影残差。截面顶点位于杆件中点截面，顺序为 `(0,0),(b,0),(b,t),(t,t),(t,b),(0,b)`，然后移至形心坐标并按朝向旋转。
3. `edge_pixels`：Nx2 像素到投影实体边的最近距离。实体边包含两端截面边与六条纵向边，排除端面三角化的虚假对角线。尚未实现遮挡剔除；输入必须只提供已确认可见、可用且关联正确的边缘。
4. `image_width`、`image_edge_gap`：简化但由实体截面生成的像素宽度/外角与内角间距；实测字段为 `value_px`。
5. `lidar_edge_gap`：沿 `scan_direction` 的已关联内外角间距；实测字段为 `value_m`。
6. `thickness`：现场厚度测量，含 `value_m`、`sigma_m`，共同参与候选更新。

所有影像类型需要 `K`（3×3 内参）、`R`（正交世界到相机旋转）、`t_m`（长度为 3），使用 `X_camera=R X_world+t_m`，含 `sigma_px`。拒绝在相机平面或背后的已声明可用特征。未实现镜头畸变、相机联合标定、自动照片关联和完整可见性判断；应先去畸变并提供标定及人工/外部算法关联。

建议提供 `measurement_id` 标识独立来源；提供时必须为唯一非空字符串，同 ID 重复会报错。不同 ID 或缺少 ID 都不能证明独立；同帧、重复点、同一次测厚的复制以及其他相关数据必须外部聚合、去重或协方差白化。本版不估计观测相关性，返回 `measurement_independence` 说明这一假设。

## 观测一致性与工程决策门控

先检查绝对残差，再比较候选相对权重。自由度为有效残差数减拟合参数数；在已声明独立、白化、近高斯残差假设下，以 nominal chi-square p 值低于 0.001 作不适配诊断。自由度不正时不能把完美拟合当证据；参数贴边、局部秩不足另列警告。这个 p 值不是经现场数据验证的置信覆盖率。

全部候选不适配、20 mm 测厚越出 8/10 mm 候选库、精密测厚互相矛盾时，返回复核/扩库任务，禁止选择旧规格库里的最近值。仅端点观测不能消除厚度歧义；先验 1e10:1 也不能把该状态称为测量支持。空图像对应、缺少材料或非正噪声直接拒绝。

顶层 `engineering_decision` 仅有 `undetermined` 与 `report_conditionally`。后者仅允许在明确简化模型及给定条件下报告，不能解释为工程合格、规范 PASS 或安全证明。失效/未知观测模型、缺杆机构、无证据和仍存在联合决策分歧均保持未决。

## 力学与补测范围

实现 3D 铰接轴向桁架的刚度装配、约束求解、轴力、反力、能量及全局力平衡。截面积和惯性由不重叠的两个矩形精确积分；筛查容量取截面屈服，受压时再与弱轴 Euler 容量取较小值，使用显式有效长度系数（缺省 1，列为模型假设）。

不包括梁弯曲、连接偏心、滑移、螺栓孔净面积、局部屈曲、初始缺陷、残余应力、腐蚀分布或规范分项系数。`below_screening_limit` 仅表示给定简化模型下低于筛查阈值。真实缺杆导致机构时返回 `mechanism_or_unresolved`，不会增加虚构杆件使模型稳定。

候选厚度组合精确枚举（默认最多 4096 个组合；联合候选两两检查默认最多 50000 次；超预算报错，不偷偷丢弃组合）。保存每个联合候选 ID 及完整杆件筛查决策向量，比较完整向量形成分歧对。不能仅比较每根杆件的边际决策集合，否则六杆等例会漏掉真实系统分歧。

预测动作对这些联合分歧对的观测差异，以噪声归一化。达到阈值（默认 3 个噪声单位）的对列为未来可区分；没有达到的保留。一个杆件测量可以减少部分分歧，而不必一次消除全部；动作输出可分离对、未分离对、覆盖率及 `resolves_all_current_pairs`。顺序采集后重算，直至没有已建模分歧或保留未决。分数为覆盖度、分离度和成本的代理，没有声称是完整 Bayesian VoI，也没有把模型概率当安全保证。

## 输出与可视化

`result.json` 包含 `members`（候选、权重、优化诊断、筛查利用率、状态）、`actions`、`geometry`、原始 `measurements`、`material`、`supports`、`loads`、`solver`、`limitations` 和输入 `case`。

- `geometry.members[].mesh.vertices_m/triangles`：完整有限厚度 L 型实体表面，包括内外表面、端边和两端面，可供浏览器直接显示。
- `surface_gaussians.ply`：物理表面确定的扁平高斯，包括标准属性 `x/y/z`、`f_dc_0..2`、logit `opacity`、log `scale_0..2`、`rot_0..3`（wxyz）。法向厚度尺度 10 μm 用于工程表面显示，不是杆件物理厚度。
- `gaussian_members.json`：每杆件的首高斯索引、数量和显示截面参数，与 PLY 逐行一致。

没有进行影像损失训练或学习真实颜色/透明度。歧义未解除时可视化只显示一个条件性最高权重模型，`display_is_conditional:true` 明确标识；不能把该显示截面当已证实实物。

## 演示与验证

演示是人工合成的 1 m 三杆支撑结构，显式 E=200 GPa、fy=355 MPa，600 kN 竖向压力；不是真实输电塔或实测数据。M1 肢宽 100 mm、厚度 8/10 mm。声明的遥测分辨率下，两候选权重接近 0.5；8 mm 与 10 mm 分别超过/低于简化轴向筛查阈值。追加 10 mm±0.15 mm 合成测厚后，候选歧义解除，补测需求下降。

有意义测试覆盖截面解析面积/惯性、闭合实体体积、针孔相机及非法矩阵、有限厚度表面距离、联合 LiDAR/影像肢宽朝向拟合、FE 轴力与力平衡/能量、8/10 mm 分歧及测厚更新、真实缺杆机构、单位/材料/负厚/噪声校验、高斯文件映射。测试不构成现场性能、规范符合性或专利新颖性的验证。

另有回归测试检查：20 mm 库外读数、矛盾测厚、端点＋强先验、空观测、自由度不足、单候选未经证实、同 measurement_id 重复来源以及六杆 64 联合候选分歧/部分测量覆盖。当前共 23 项通过。

`data/calibrated_geometry_case.json` 是另一个合成针孔相机/LiDAR 关联几何拟合案例，真实生成参数为肢宽 100 mm、朝向 0.18 rad、厚度 10 mm，初始为 90 mm/0 rad；声明的较宽噪声及束足迹下仍保留 8/10 mm 多解。它使用无噪声生成的特征均值和非零声明不确定度，不是实测数据或实际标定相机。`data/calibrated_geometry_result/` 提供计算结果和 PLY。可直接用 CLI `--case` 读取。
