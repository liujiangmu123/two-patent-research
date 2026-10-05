# 开源技术与商业部署清单

核验日期：2026-10-03。首版路线：现成无人机采集原始资料，地面工作站处理，必要时安排现场测厚。本文是集成设计清单，不表示候选库已经安装、模型已经下载或生产系统已经集成。

## 选型结论

首版数值实现以 NumPy、SciPy 和自研有限厚度几何/三维轴向桁架程序为核心，网页已集成 Three.js r180；可选使用 Open3D 做点云检查、OpenCV 做标定、COLMAP 做影像配准。GPU 工程阶段拟采用 PyTorch 与 gsplat 自行实现有限厚度角钢表面的可微渲染。SAM 2 仅辅助掩膜与人工校正，不能提供截面厚度真值。候选用途与许可证证据见 `projects.csv`；当前实际集成版本与Three逐文件哈希见 `INTEGRATED_NOTICE.md`。

建议的算法链为：标定及原始资料审计 → 初始桁架图 → 参数决定角钢内外表面 → 相机/LiDAR 观测预测 → 保留不能区分的规格 → 承载结论分歧 → 补测及回灌。通用高斯重建软件可以用于展示、初值和比较，不能直接把自由高斯坐标当杆件尺寸。

## 许可实际约束

- 原始 [2DGS](https://github.com/hbb1/2d-gaussian-splatting/blob/main/LICENSE.md) 代码只允许非商业研究/评估。工程版采用获准后端或自行实现表面高斯，不复制该受限代码进入交付物。
- [VGGT-Ω](https://github.com/facebookresearch/vggt-omega/blob/main/LICENSE) 当前为非商业研究许可，包含输出的商业使用限制及用途约束。只列为研究资料；不下载、不运行，也不作为本工程核心依赖。原 VGGT 商业权重需另核验具体许可和用途。
- [gsplat](https://github.com/nerfstudio-project/gsplat/blob/main/LICENSE)、[SAM 2](https://github.com/facebookresearch/sam2/blob/main/LICENSE) 为 Apache-2.0；COLMAP、PyTorch 等第三方依赖仍需随实际构建检查。本清单核验的是指定项目主体许可，不自动覆盖其全部依赖、预训练权重和数据集。

## 代码/模型/数据分开管理

每次交付生成软件物料表，记录项目版本、提交号、下载来源、wheel 或源码 SHA-256、许可证与 NOTICE。模型另列权重哈希及权重许可；数据另列采集授权、处理权限和脱敏规则。保留本工程自研角钢生成、不可辨规格保留和补测选择代码的原创记录。

未下载大模型，未克隆大型仓库，未改动已有 A 专利原文。当前项目虚拟环境的 NumPy 2.5.3、SciPy 1.18.1已实际用于CPU API与独立测试，Three.js r180已纳入本地三维查看器；回归结果以软件测试及 `../validation/AUDIT.md` 为准。禁止将清单中的“拟集成”写成“已工业验证”。

版本锁定执行见 `LOCK_POLICY.md`；硬件资料见 `../hardware/README.md`；现场验证见 `../validation/field/FIELD_TRIAL_PROTOCOL.md`。
