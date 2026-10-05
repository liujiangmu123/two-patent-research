# 公开前案对比与检索边界

检索核验日：2026-10-03。目的：比较申请草稿的技术区别，不作授权承诺或实施自由保证。仅检索用户指定刘智远专利目录及公开网络。未检出完全相同组合不等于未申请，未公开申请、数据库索引遗漏、不同术语和同族翻译均可能形成盲区。

申请草稿主核编号：C1 共享节点及有限厚度 L 实体参数唯一生成观测几何；C2 保留同宽异厚等观测等价规格；C3 将候选映射至承载验算分歧；C4 对判定分歧候选对预测噪声归一化测量分离度；C5 遥测无效时转局部测厚并回灌同一模型；C6 候选遗漏风险受控情况下按判定一致性停止，真实缺材不为稳定补杆。下表“不见”仅表示已读公开文本未找到该具体机制，不是对所有申请的否定。

| 编号与来源 | 申请人/来源方、首次公开日 | 已核对内容 | 草稿应保留的区别及风险 |
|---|---|---|---|
| [CN120976438A](https://patents.google.com/patent/CN120976438A/zh) | 南京邮电大学；2025-11-18 | 全部9项中文权利要求；独权1为影像/LiDAR、Z层质心骨架、高斯特征对齐、等密度面、Poisson网格、顶点与高斯参数联合优化。权7有三角形重心坐标绑定高斯。 | 不见C1的有限厚度角钢共享节点作为唯一几何自由度，亦不见C2—C6闭环。不能把“图/骨架约束高斯”笼统称新。 |
| [CN121685855A](https://patents.google.com/patent/CN121685855A/zh) | Zhongchen Kejie Design Engineering Co ltd；Tianjin University Research Institute of Architectural Design and Urban Planning；2026-03-17 | 独权1：钢构影像、质量掩膜、可见性权重、直线/平面/圆形结构引导、高斯分裂合并及边界一致性。权7独立优化各高斯中心、协方差、透明度。 | 一般钢构高斯重建和结构引导已经公开；C1需明确有限实体及工程参数生成约束，重点结合C2—C5。申请人中文正式全称应以申请公报再核，避免由英文推译。 |
| [CN121190660B](https://patents.google.com/patent/CN121190660B/zh) | 中国矿业大学（北京）；A首次公开2025-12-23 | 已读B独权1：激光/视觉时空标定、高斯初始化、光度与几何一致性、线/面约束、自适应密度。 | 双模态高斯融合本身不新；不见有限角钢候选承载分歧与测厚切换。首次公开日采用A，而非B授权公开日2026-02-24。 |
| [CN117933030A](https://patents.google.com/patent/CN117933030A/zh) 与 [B](https://patents.google.com/patent/CN117933030B/zh) | China South Power Grid International Co ltd（南方电网国际）；2024-04-26 | 点云分割、角钢截面参数与规格表匹配、建立输电铁塔有限元模型。 | 从点云得到规格并输出FE已公开；区别应放在不强制唯一规格、观测等价候选及判定分歧动作选择。不能沿用旧查新文件的申请人推断。 |
| [CN121185202A](https://patents.google.com/patent/CN121185202A/zh) | Shandong Zhonghe Land Real Estate Appraisal Co ltd；2025-12-23 | 独权1为地下管道多源数据两级校正及三维形变量化；权4以参数不确定度调整微激励，权10对弱可观测区段反向补测。说明书有物理前向反演和不可辨识标记。 | 一般可观测性驱动采集不是新的。未检出明确奇异值/秩检验，不能将该细节错误归给前案；本案C3—C5的角钢厚度与承载分歧关联需具体。 |
| [US10451416B1](https://patents.google.com/patent/US10451416B1/en) | Bentley Systems Inc；2019-10-22 | 独权1使用信息矩阵、信息熵或总模态能量、遗传算法优化结构健康监测传感器布置。 | 不以“信息矩阵＋结构＋测量选择”为新颖性主张；本案针对具体观测等价规格与跨测量类型闭环。 |
| [CN121434682A](https://patents.google.com/patent/CN121434682A/zh) | 国网河南省电力公司洛阳供电公司；2026-01-30 | 配电网数字孪生、设备映射、风险热度、知识图谱和多目标巡检；说明书有角钢塔参数模板及点云配准。 | 泛参数化数字孪生与风险巡检已公开，不見C2—C5的测厚闭环；不能只以工业对象或数字孪生命名避开前案。 |
| [SplatAD](https://arxiv.org/abs/2411.16816) / [CVPR原文](https://openaccess.thecvf.com/content/CVPR2025/papers/Hess_SplatAD_Real-Time_Lidar_and_Camera_Rendering_with_3D_Gaussian_Splatting_CVPR_2025_paper.pdf) | Hess等；arXiv首次2024-11-25，CVPR2025 | 同一高斯场相机与LiDAR渲染、距离/强度/掉点、光束发散处理及视线约束。 | 不宣称首次高斯激光渲染、首次无回波或首次束足迹。可作为物理观测实现参考，不能代替本案有限厚度参数约束。 |
| [GaussianPlant](https://arxiv.org/abs/2512.14087) | 原论文作者；2025-12-16 | 结构基元绑定外观高斯并优化基元参数。 | “几何基元绑定高斯”一般思路已知，独权不能仅写参数绑定。 |
| [FisherRF](https://arxiv.org/abs/2311.17874) | 原论文作者；2023-11-29 | Fisher信息指导主动三维重建视点。 | 泛信息增益NBV成熟，C4应限定判定分歧候选对，C5应限定预测遥测不能区分时的测厚切换。 |
| [Sensor informativeness, identifiability and uncertainty…](https://fis.tu-dresden.de/portal/en/publications/sensor-informativeness-identifiability-and-uncertainty-in-bayesian-inverse-problems-for-structural-health-monitoring%2893c7d430-35c7-4eff-9d6f-99aa485ac79b%29.html) | TU Dresden论文记录；2026-08-01 | 结构健康监测贝叶斯反演中的传感信息、可辨识性和不确定度，MSSP 257，114606。 | 可借鉴尺度与干扰处理，不能声称可辨识性门控本身首次提出。 |

CN120976438A 的 web 解析入口曾失败，随后用只读 HTTP 获取 Google Patents 中文 HTML，核对完整9项权利要求及日期/申请人元数据；未取得官方PDF。其 [镜像](https://www.goveda.com/patent/CN-120976438-A) 用作交叉核验，公式缺失的机器翻译不作为唯一依据。

检索词覆盖中文角钢/输电塔/高斯/反演/截面/可辨识性/候选/承载/补测，以及英文 parametric angle steel、surfel graph、LiDAR image inverse、observability、structural hypotheses、measurement selection、thickness 等组合。此次未做完整分类号、全部同族、审查档案或实施自由分析。

保守结论：C1—C5具备值得继续工程验证与申请布局的具体技术联系，但申请草稿是方案，不是已验证结果。审查可能认为这些特征可由参数化重建、已知可辨识性设计和决策测量容易组合；若未证明比通用不确定度补测更有效的条件与效果，可申请性仍有限。正式提交前应围绕这一组合做分类号/引用链查新，核对实际实现对独权的支持，并由代理人审阅。

验证应优先建立同宽异厚且遥测受限的对照样件，在可信荷载/连接条件下形成工程判定分歧，再证明模式切换能够解决该分歧。无需宣称所有肢厚都能远程识别，也无需为渲染质量堆砌通用算法。
