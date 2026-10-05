# 实际集成的软件与许可记录

核验日期：2026-10-03。本表记录当前交付物的实际使用状态；`projects.csv`仍保留候选技术选型。软件运行及浏览器验收记录由总体交付记录维护；本次独立审计实际运行CPU API与pytest，并核验本地Three源文件。

|项目|冻结版本|当前用途与实际状态|主体许可与证据|
|---|---|---|---|
|NumPy|2.5.3|已由CPU几何、三维轴向桁架求解与独立审计实际调用|BSD-3-Clause；[官方LICENSE](https://github.com/numpy/numpy/blob/main/LICENSE.txt)；本地`.venv/Lib/site-packages/numpy-2.5.3.dist-info/licenses/`还含第三方声明|
|SciPy|1.18.1|已由least_squares、统计chi-square诊断、logsumexp与旋转表示实际调用|BSD-3-Clause主体；[官方LICENSE](https://github.com/scipy/scipy/blob/main/LICENSE.txt)；本地`.venv/Lib/site-packages/scipy-1.18.1.dist-info/LICENSE.txt`及所带依赖声明须随实际二进制发布保留|
|Three.js|r180|已集成本地网页三维查看器；`app.js`导入Three与OrbitControls，`index.html`提供本地import map；显示工程网格与表面采样|MIT；[r180官方LICENSE](https://github.com/mrdoob/three.js/blob/r180/LICENSE)；完整许可已随`software/web/vendor/three/LICENSE`携带|

当前环境Python查询值为3.14.6，实际执行入口始终是项目`.venv/Scripts/python.exe`。使用已安装版本通过CPU测试不代表NumPy/SciPy所有二进制第三方组件的发布审计已经完成；正式分发环境须携带该具体构建所需的许可文件并锁定wheel/解释器哈希。

## Three.js来源与逐文件完整性

本地目录：`software/web/vendor/three/`。独立审计直接从官方`mrdoob/three.js`的`r180`标签读取同名文件，分别计算原始字节SHA-256。下列四个本地文件与官方标签文件逐字节一致，没有重写OrbitControls导入。离线import map负责解析其`three`导入。

|本地文件|字节数|SHA-256（本地与官方相同）|官方固定来源|
|---|---:|---|---|
|three.module.js|603113|`c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a`|[r180/build/three.module.js](https://raw.githubusercontent.com/mrdoob/three.js/r180/build/three.module.js)|
|three.core.js|1403455|`eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20`|[r180/build/three.core.js](https://raw.githubusercontent.com/mrdoob/three.js/r180/build/three.core.js)|
|OrbitControls.js|38703|`b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c`|[r180/examples/jsm/controls/OrbitControls.js](https://raw.githubusercontent.com/mrdoob/three.js/r180/examples/jsm/controls/OrbitControls.js)|
|LICENSE|1081|`bfe119ea4fd413f5f7ca3fcd63adb0c4a073ed39daa2fe7d3e6b769e21272601`|[r180/LICENSE](https://raw.githubusercontent.com/mrdoob/three.js/r180/LICENSE)|

Three.js的MIT许可要求在复制或实质性分发时保留版权及许可声明。该许可已随vendor文件保留，正式交付应继续包含此文件；不把哈希核验解释成第三方代码安全认证。

## 候选与研究参考

OpenCV、Open3D、COLMAP、PyTorch、gsplat、SAM 2、SplatAD及Livox SDK为后续工程阶段的候选或可选接口，当前核心和网页未导入这些库。本工程没有下载或训练SAM/VGGT等大模型。原始2DGS、VGGT-Ω及SurfFill仅作为论文/许可研究资料，未复制受限实现进入商业交付。

当前PLY由自研有限厚度角钢表面确定性采样生成，颜色与不透明度为赋值；Three.js显示这些工程结果。两者均不构成已完成照片训练的3DGS/2DGS系统、已集成gsplat或已验证真实无人机测量精度的证据。

后续集成改变时，同时更新本文、`projects.csv`、环境锁与真实回归记录；保留主体、二进制第三方依赖、模型权重和数据许可的区别。
