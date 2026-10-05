# 首版数据与本地 API 约定

版本：2026-10-03，`trusstwin.case-result/0.1`。本文记录 `software/trusstwin/pipeline.py`、`observations.py` 和 `software/serve.py` 的实际读取字段及行为。首版正式冻结为**现成无人机导出数据＋地面工作站＋经人工或外部算法关联的观测**。协议设计、可运行原型与现场能力分别登记。

## 1. 当前输入范围

Python：`run_case(case_dict, output_dir=None)`；示例生成器：`demo_case(with_thickness=False)`、`geometry_demo_case()`。CLI 接受 `--demo` 或 `--case JSON`，`--out` 指定输出目录。仅使用项目根 `.venv`。

当前不直接读取原始照片、LAS/PCD、CAD、现场测厚 CSV 或 LiDAR 原始包。需要先形成下列 JSON，关联杆件、整理坐标、去畸变并提供固定标定。尚无 PTM 自动结构图提取、自动杆件关联、时间同步解算、gsplat/GPU 实景训练或原始射线适配器。未知扩展字段可随 `case` 保存，但不意味着程序已经利用该字段作推断或验算。

## 2. 项目 JSON

全局单位字段必须是 `"units":"m-N-Pa"`，内部使用米、牛顿、帕、弧度和 m⁴。禁止依据数值大小猜测单位。以下是一个可运行的**最小合成算例**，不是实际杆塔工况：

```json
{
  "name": "最小合成单杆算例",
  "synthetic": true,
  "units": "m-N-Pa",
  "nodes": {"base": [0, 0, 0], "top": [0, 0, 1]},
  "members": [{
    "id": "M1", "nodes": ["base", "top"],
    "width_m": 0.100, "thickness_candidates_m": [0.008, 0.010],
    "orientation_rad": 0, "effective_length_factor": 1
  }],
  "material": {"E_Pa": 200000000000, "yield_strength_Pa": 355000000},
  "supports": [{"node": "base", "dofs": [0, 1, 2]}, {"node": "top", "dofs": [0, 1]}],
  "loads": [{"node": "top", "force_N": [0, 0, -600000]}],
  "measurements": [{
    "measurement_id": "synthetic-UT-001", "kind": "thickness", "member_id": "M1",
    "value_m": 0.010, "sigma_m": 0.00015
  }]
}
```

| 字段 | 实际约定 |
|---|---|
| `nodes` | 对象 `{节点ID:[x,y,z]}`；至少两个节点，坐标有限。多个杆件引用同一 ID，共享同一位置。当前坐标固定，不联合优化节点。 |
| `members` | 非空数组；唯一字符串 `id`、两个有效节点 `nodes`、正 `width_m`、非空且不重复的 `thickness_candidates_m`。各截面须满足 `0<t<b`；杆件长度非零。 |
| `orientation_rad` | 可选，缺省 0。杆件局部 z 从起点指向终点；程序选与轴最不平行的全局参考轴，构建正交截面基，再绕杆件轴旋转。杆件线是截面形心线。不是任意 CAD 局部坐标的直接复用。 |
| `exists` | 可选布尔，缺省 true。false 保留真实缺杆输入，几何与刚度中不插入该杆；这是用户给定状态，不是已实现的缺杆检测。 |
| `candidate_priors` | 可选，与厚度候选等长的正数数组，内部归一化。与观测支持分开；强先验不能删除观测等价候选。 |
| `effective_length_factor` | 正数，缺省 1。仅用于简化弱轴 Euler 筛查；不能自动推断实际连接有效长度。 |
| `section_source` | 固定单候选来源。`verified_as_built` 或合成示例的 `synthetic_known_input` 是显式来源声明，软件不自动核验其真实性；未提供来源且无有效测厚时不得称为厚度测量支持。 |
| `material` | 必须显式提供正 `E_Pa` 和 `yield_strength_Pa`；不能猜钢号。额外材料调查、来源、区间、塑性参数当前不自动读取。 |
| `supports` | 必须提供数组，节点有效，`dofs` 是非空 0/1/2 列表，对应全局 x/y/z 平移约束。 |
| `loads` | 必须提供数组，节点有效，`force_N` 是有限三向节点力。当前是一组线性静力节点荷载；没有荷载规范生成器或自动荷载组合。 |
| `measurements` | 可选数组；每条必须关联有效 `member_id`、支持的 `kind` 和正噪声标准差。 |
| `planned_actions` | 可选动作模板，含 `kind`、`member_id`、预测所需相机/方向、噪声及正 `cost_units`。这不是飞控指令或仪器驱动。 |
| `candidate_probability_floor` | 可选，缺省 0.01，范围 `[0,0.5)`；用于 likelihood-only 候选保留。尚无严谨的截断风险上界。 |
| `measurement_separation_threshold` | 可选正数，缺省 3 个声明噪声单位，是算法门槛而非现场安全标准。 |
| `nominal_fit_rejection_alpha` | 可选，缺省 0.001，须在 `(0,0.1)`；绝对拟合的 nominal χ² 诊断阈值。 |
| `max_joint_candidates` / `max_joint_pair_checks` | 缺省 4096 / 50000；超预算报错，不静默截断后宣称一致或停止。 |
| `gaussian_spacing_m` | 缺省 0.10，范围 `(0,1]`；控制工程表面面元采样。 |

连续拟合在成员内显式开启：

```json
"fit": {
  "width": true, "orientation": true,
  "width_bounds_m": [0.080, 0.120],
  "orientation_bounds_rad": [-0.4, 0.4]
}
```

边界必须包围初值，宽度下界大于全部候选厚度。每个离散厚度内部用 SciPy least_squares 拟合肢宽/朝向。节点、相机、材料、荷载与边界保持输入值；未实现完整混合因子图、外参/时间偏移/节点联合估计。

## 3. 已支持的观测字段

| `kind` | 实际字段及残差 |
|---|---|
| `lidar_points` | `points_m` 非空有限 Nx3、正 `sigma_m`；可选非负 `beam_diameter_m`。残差是点到有限厚度三角表面的最近距离。束足迹仅加到标量误差：`sqrt(sigma_m²+beam_diameter_m²/12)`。没有实际射线追踪、束积分、强度、遮挡或回波概率。 |
| `image_points` | 非空 Nx2 `pixels`、正 `sigma_px`、相机 K/R/t；`feature` 为 `section_vertices` 或 `endpoints`，`indices` 为非空合法索引。逐像素针孔重投影残差；关联由输入方提供。 |
| `edge_pixels` | 非空有限 Nx2 `pixels`、`sigma_px`、K/R/t。像素到投影实体边的最近距离；端面三角化对角线不作为实体边。当前不剔除遮挡边，输入方须限定可见、关联正确的特征。 |
| `image_width` | `value_px`、`sigma_px`、K/R/t；使用杆件中部截面的投影包围宽度。 |
| `image_edge_gap` | `value_px`、`sigma_px`、K/R/t；使用已关联外角与内角的投影间距。不是自动图像测厚算法。 |
| `lidar_edge_gap` | `value_m`、`sigma_m`、可选 `beam_diameter_m`、非零三向 `scan_direction`；内外角沿扫描方向的差异。方向内部归一化。 |
| `thickness` | 正 `value_m`、正 `sigma_m`；作为已关联的单一均匀杆件厚度观测。当前不读取肢、纵向点位、局部腐蚀场、涂层或温度模型。 |

通用字段 `measurement_id` 若提供，必须是全项目唯一非空字符串。重复 ID 会拒绝，防止复制一条读数制造证据。不同 ID、缺 ID 或同一条点数组内部的多个点**并不证明独立**；同帧、同点、同次仪器测量的相关性须在外部聚合、去重或协方差白化。本原型没有自动相关性估计。`visible:false` 的观测拒绝用于推断；它不是自动可见性检测器。

### 相机与特征索引

`K` 为 3×3，正 `fx/fy`、最后一行 `[0,0,1]`；`R` 为 det=+1 的正交世界到相机旋转；`t_m` 是长度为 3 的米制平移。约定：

`X_camera = R X_world + t_m`；`pixel = K X_camera / Z_camera`。

像素原点、K 与输入图像须一致。当前**没有畸变模型**，必须先去畸变，并使用去畸变后的 K；不能传入畸变原图上的像素却沿用理想针孔解释。位于相机平面或背后的已声明有效特征会拒绝。

`endpoints` 索引 0/1 是共享节点的起点/终点。`section_vertices` 索引 0–5 是杆件中点截面的 `(0,0),(b,0),(b,t),(t,t),(t,b),(0,b)`，移至形心后按局部基和朝向转至世界。只有端点像素没有厚度信息，不能据此确认厚度。

### 测厚单位与边界转换

API **只接受米**：10 mm 与 0.15 mm 标准差必须转换为 `value_m=0.010`、`sigma_m=0.00015`。网页表单展示毫米，提交前明确除以 1000；核心不猜单位。直接请求传入 `10` 就是 10 m，不会自动当 10 mm。

现场表格应保留原始毫米读数、仪器/校准、肢/点位、温度、涂层、耦合和重复性证据。当前表单只传杆件、米制值和标准差，尚无完整现场 CSV 适配器或多点最小厚度模型；局部健康点不能因此自动代表整杆最小有效厚度。

## 4. 本地 HTTP 路由

默认 `http://127.0.0.1:8767`，可通过 `serve.py --port` 修改；仅绑定本地回环。无设备驱动、WebSocket、飞控或云 API。POST 接受 JSON 对象，最大 4 MiB；非同源 Origin 请求拒绝。路径按下面的实际路由使用。

| 方法/路径 | 请求 | 响应/作用 |
|---|---|---|
| GET `/api/health` | 无 | `{status:"ok",version:"0.1.0"}`。只表示 HTTP 服务可响应，不代表传感器在线或工程结果有效。 |
| GET `/api/project` | 无 | 当前 `{case,result,build}`。 |
| POST `/api/run` | `{"case":项目JSON}`，也可直接提交项目对象 | 验证、计算、成功后保存并返回 `{case,result,build}`。 |
| POST `/api/demo` | `{}` 或 `{"with_thickness":true}` | 重置为合成演示，可含合成 10 mm 测厚。不能称为实测。 |
| POST `/api/measurement` | `{"measurement":{"kind":"thickness","member_id":"M1","measurement_id":"UT-001","value_m":0.010,"sigma_m":0.00015}}`，或直接测量对象 | 仅接受 thickness，追加至当前 case，重算后返回快照。其他观测通过 `/api/run` 导入。 |
| GET `/export/result.json` | 无 | 当前计算结果。 |
| GET `/export/case.json` | 无 | 当前输入项目。 |
| GET `/export/surface_gaussians.ply` | 无 | 由物理参数生成的工程表面高斯。 |
| GET `/export/gaussian_members.json` | 无 | PLY 索引到杆件与显示截面的映射。 |

服务使用暂存目录先计算，再在锁内发布成功文件。失败请求保持上一次成功项目；**该旧结果不能解释为失败新输入的结论**。没有完整的多版本证据库、用户鉴权或崩溃级事务保证。

错误响应为 `{"error":"原因"}`：422 为输入/几何/求解预算等计算拒绝，413 为空体或超 4 MiB，403 为非同源写入，404 为未知路由/导出/不存在文件，400 可用于非法静态路径，500 为未处理的计算异常。CLI 对可识别输入错误返回退出码 2。机构属于计算结果的未决状态，不应伪装 HTTP 成功即验算通过。

## 5. 输出口径与新门控字段

顶层 `engineering_decision` 仅为 `undetermined` 或 `report_conditionally`；后者只在声明的简化模型和输入假设下报告，**不是规范 PASS 或安全证明**。`solver.status=solved` 只表示矩阵求解完成。

| 输出 | 含义 |
|---|---|
| `members[].posterior` / `prior_weights` / `likelihood_only_weights` | 分别为先验结合 profile likelihood 的权重、先验、纯观测相对权重。候选保留及规划使用 likelihood-only；三者均不是经现场校准的安全概率。 |
| `members[].candidates` | `candidate_id`、厚度/拟合宽度/朝向、截面性质、chi_square、有效 residual_count、fit_degrees_of_freedom、nominal_fit_p_value、absolute_fit_consistent、retained、优化状态/局部秩/边界警告及条件性筛查利用率。 |
| `members[].evidence_summary` | `has_effective_residuals`、`any_absolute_fit_consistent`、`all_candidates_rejected`、`conflicting_thickness_observations`、`outside_candidate_library`、诊断假设、rejection_alpha、`no_safety_probability_claim:true`。 |
| `members[].status` | 支持状态包括 input_fixed_section、measurement_supported_candidate；未决/复核包括 screening_disagreement、geometric_ambiguity_same_screening_decision、outside_candidate_library、inconsistent_observations、observation_model_mismatch、insufficient_fit_degrees_of_freedom、parameter_bound_warning、local_identifiability_warning、unverified_single_section_input、missing_member、structural_model_unresolved。 |
| `joint_disagreement` / `unresolved_joint_pair_count` | 比较完整联合候选的杆件决策向量，不能用相同边际集合推断整体一致。 |
| `solver.mechanics_cases` | 每组合 ID、候选 ID、条件权重、完整 decision_vector、observation_admissible 和计算诊断。保留的 debug 组合不一定有观测资格。 |
| `actions` | 普通测量有模板、噪声归一化 separation_sigma、门槛、有效性与覆盖代理分数。separable_joint_pair_ids 是**未来可分离**的对，尚未解除；unseparated_joint_pair_ids、覆盖数量/比例及 resolves_all_current_pairs 说明剩余分歧。 |
| 复核动作 | expand_candidate_library_and_review_measurement、review_observation_model_and_repeat_measurement、verify_section_assumption，含 requires_review=true、reason，effective=false；不含可执行测量模板，不能作为飞控/仪器指令。 |
| `geometry` | 共享节点、实体三角面、显示候选与 display_is_conditional、display_observation_model_valid、高斯数量和映射。歧义或数据不相容时不能把显示截面当证实实物。 |
| `measurement_independence` / `limitations` | 来源 ID 数量、独立性假设及未实现范围。必须与权重一起阅读。 |

相对权重即使归一化到 1，也不能掩盖全部候选绝对不适配。nominal χ² 只在声明的独立白化近高斯残差假设下作诊断；自由度≤0不成立。库外测厚、观测矛盾、拟合边界、局部不可辨及缺杆机构均进入复核/未决。

## 6. 与 TS-01 未来协议的区别

`hardware/SYNC_DATA_PROTOCOL.md` 是未在实物设备运行的设计规格，包含任务相对整数 ns、UTC 锚点、曝光中点、逐束时间、时钟段及无回波资格。**本 API 不消费这些逐事件字段，也不实现其硬同步或时偏解算。**

| 能力等级 | TS-01 设计含义 | 本原型状态 |
|---|---|---|
| C0 | 原图/处理点云，缺少逐束轨迹 | 仅支持已关联图像特征和米制点；原图自动处理仍未实现。 |
| C1 | 有效回波、时间、姿态和可恢复方向 | 未有设备包适配器或逐点去运动；输入点应已在统一坐标中。不能宣称已验证 C1。 |
| C2 | 发射计数/invalid 槽，但方向或原因不足 | 未实现原始事件质检、覆盖计数。 |
| C3 | 每次发射、方向、返回状态及健康/丢包/门限可核验 | 未实现完整返回概率或 eligible_no_return 因子；没有证明现有设备提供 C3。 |

点缺失、全零点、未看见杆件或包丢失均不能转为无回波负证据。`beam_diameter_m` 的误差近似**不等于 C3 或完整激光束前向模型**。后续适配器必须保留原始时间尺度、时戳定义、校准版本、排除原因和资格证据，经过台架/现场验证后才能启用对应机制。

当前 3D 桁架仅做 gross-section 轴向屈服/弱轴 Euler 筛查。材料、连接和荷载调查、区间传播、梁弯曲/偏心、局部屈曲、孔洞净面积、规范分项系数及完整承载认证均未实现。
