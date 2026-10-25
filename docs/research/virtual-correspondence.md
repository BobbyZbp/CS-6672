# Virtual correspondence / virtual views：GhostMap 的适用边界与实验方案

调研日期：2026-10-23。本文是长期项目规划依据，不表示下列新算法已在 Cornell 数据上运行或通过验证。

## 1. 先澄清名称，避免把三类不同问题混为一谈

用户所说的 “virtual corresponding” 尚无论文链接，不能认定具体指哪篇。至少有以下三种合理解释：

| 解释 | 已核对的一手工作 | 实际解决什么 | GhostMap 中的角色 |
|---|---|---|---|
| 专有名词 **Virtual Correspondence** | Ma et al., CVPR 2022, *Humans as a Cue for Extreme-View Geometry* | 利用同一个静止人体的形状先验，在几乎不共视的图像之间估计相机关系 | 理论参考，不作为校园建筑重建的现成模块 |
| 从已有场景渲染虚拟视角，再匹配 / 验证相机 | InLoc, CVPR 2018；MeshLoc, ECCV 2022 | 已有可信 3D 地图，求真实查询照片的相机位姿 | 现代 Arts Quad 重建完成后的重要定位基线 |
| 用学习几何 / 神经渲染补充虚拟关键帧 | GPVK-VL, CVPR 2025；与 DUSt3R / MASt3R 等有关 | 缓解参考照片与查询照片的视角差异 | 需要单独消融、标记先验依赖的研究分支 |

这些工作都不意味着“生成一些新照片，就获得了更多真实多视角观测”。现代场景的第一优先级仍是获得真实的跨建筑重叠、正确相机和多视角稠密几何。

## 2. 专有名词 Virtual Correspondence：读过原论文后的结论

**Wei-Chiu Ma, Anqi Joyce Yang, Shenlong Wang, Raquel Urtasun, Antonio Torralba. Virtual Correspondence: Humans as a Cue for Extreme-View Geometry. CVPR 2022.** 不是 Noah Snavely 的论文。

- [CVF 论文页](https://openaccess.thecvf.com/content/CVPR2022/html/Ma_Virtual_Correspondence_Humans_as_a_Cue_for_Extreme-View_Geometry_CVPR_2022_paper.html)
- [正式 PDF](https://openaccess.thecvf.com/content/CVPR2022/papers/Ma_Virtual_Correspondence_Humans_as_a_Cue_for_Extreme-View_Geometry_CVPR_2022_paper.pdf)
- [可访问的项目页](https://virtual-correspondence.github.io/)
- 原文列出的 MIT 项目地址本次返回空内容；上面的迁移页面可正常读取。

**核对程度：** 阅读原论文定义、方法、假设、实验及限制，检查项目页。项目页目前只有 “Colab (coming soon)”，未核实可用的官方算法实现；同名 GitHub 网站仓库不是实现。

### 真正的几何含义

普通对应要求两个像素观测到同一个可见物理表面点。VC 只要求两个像素的相机射线在 3D 相交，因此两个像素可以看到物体前后两个不同表面。例如，一张照片看到人的胸部，另一张看到背部；已知身体形状可以把两条射线联系起来。VC 满足极线约束，但交点不必是双目共同可见表面。

论文先预测 SMPL 人体及其相机相对姿态，再对网格做射线求交，用 DensePose 的人体表面坐标识别另一视角对应表面。初始化使用五点法 / RANSAC；广义 BA 优化点对及相机。不能简单把所有 VC 当成普通同一 3D 点的 COLMAP feature track。

### 依赖条件

- 不同图像包含可以关联的同一个人，姿态基本不变，或其他具有可靠类别形状与表面映射的同一对象。
- 相机内参已知或已被估计；论文 Sec. 3.3 脚注明确说明这一点。
- SMPL / DensePose 预测足够准确。作者明确承认高度依赖形状先验，严重形状错误会失败。
- 场景静态。论文允许少量运动，但人体姿态显著变化会失败。
- 对汽车的展示只是类比的 proof of concept，不是任意建筑、任意年代的完整对应器。

### 对校园项目的判断

多年间拍摄的 Arts Quad 网图通常没有同一个、姿态相同的人。历史与现代照片中的人更不是共同静态标定物。因此该实现路线不能直接解决我们的问题。

把建筑 CAD / 参数化建筑模型作为形状先验，研究建筑版 VC，可以是新的研究问题，但还需可靠语义表面映射、形状误差建模和独立验证。不能以“像建筑”的先验代替 Boardman 的实测形状，也不应将其放在现代 Arts Quad 的关键路径上。

## 3. 更适合 GhostMap 的虚拟视角路线

### InLoc：虚拟视角主要用于验证候选位姿

**Hajime Taira et al. InLoc: Indoor Visual Localization with Dense Matching and View Synthesis. CVPR 2018.**

- [CVF 页面](https://openaccess.thecvf.com/content_cvpr_2018/html/Taira_InLoc_Indoor_Visual_CVPR_2018_paper.html)
- [PDF](https://openaccess.thecvf.com/content_cvpr_2018/papers/Taira_InLoc_Indoor_Visual_CVPR_2018_paper.pdf)
- [官方实现](https://github.com/HajimeTaira/InLoc_demo)

**核对程度：** 阅读原 PDF 的数据、reference pose 构造、Sec. 4 方法，及官方 README；未执行实现。老项目主页本次 TLS 连接失败，不依赖该页作证据。

输入是已配准的 RGBD 地图与真实查询照片，原数据有 Faro 激光扫描。方法先检索，做 dense matching 和 P3P-RANSAC，再在候选位姿渲染虚拟视图，比较 query 与渲染结果的局部描述子，用正负证据排序，而不是只看 inlier 数量。无几何的区域不参与该比较。

这不是从几个稀疏点凭空产生完整环境。它依赖已有高质量 3D。还要注意原 benchmark 的 reference poses 含人工匹配和人工审核，不能照搬后声称原论文已经实现我们的 zero-human 约束。

### MeshLoc：网格深度把 2D–2D 匹配提升为 2D–3D

**Vojtech Panek, Zuzana Kukelova, Torsten Sattler. MeshLoc: Mesh-Based Visual Localization. ECCV 2022.**

- [PDF](https://arxiv.org/pdf/2207.10762)
- [官方实现与数据说明](https://github.com/tsattler/meshloc_release)

**核对程度：** 阅读原 PDF 对 SfM / dense-map 定位流程、网格 / 渲染输入与误差传播的论述，及官方 README；未执行实现。

输入是与参考相机对齐的稠密网格。检索真实或渲染参考视图，进行 2D–2D 特征匹配，再用网格渲染的 depth back-project 得到 2D–3D 对应，最后 PnP / RANSAC。它可以复用新 matcher，而不必为每类特征重建整个 sparse map。论文也测试无纹理几何渲染，说明定位所需结构一致性与照片写实度不是同一个指标。

这非常适合现代 Arts Quad 作为未来历史照片的 reference map：先用仍然存在的石墙、门窗、台阶和邻楼定位照片，再研究已经消失的部分。不能把现代网格中不存在的历史建筑直接作为可匹配的真实表面。

### GPVK-VL：必须纳入已有相关工作，不能当成我们的新颖性

**Yunxuan Li, Lei Fan, Xiaoying Xing, Jianxiong Zhou, Ying Wu. GPVK-VL: Geometry-Preserving Virtual Keyframes for Visual Localization under Large Viewpoint Changes. CVPR 2025.**

- [CVF 页面](https://openaccess.thecvf.com/content/CVPR2025/html/Li_GPVK-VL_Geometry-Preserving_Virtual_Keyframes_for_Visual_Localization_under_Large_Viewpoint_CVPR_2025_paper.html)
- [PDF](https://openaccess.thecvf.com/content/CVPR2025/papers/Li_GPVK-VL_Geometry-Preserving_Virtual_Keyframes_for_Visual_Localization_under_Large_Viewpoint_CVPR_2025_paper.pdf)

**核对程度：** 阅读原论文 Sec. 1–4 与实验设定。未核实官方代码发布，不把第三方同名仓库当官方实现。

输入是 **posed reference keyframes + sparse / dense 3D representation**。DUSt3R 深度及其 confidence、DSINE 法线及其 uncertainty 用于正则化 2D Gaussian Splatting；通过 reference poses 融合得到 TSDF mesh；在有效位置渲染虚拟 RGB / depth 关键帧，再用 hloc 类检索、匹配和 PnP 定位。它不是在没有参考相机或几何的情况下，凭虚拟视图证明真实建筑。

原文明确指出 generative NVS 的视觉漂亮不保证几何，且很大外推视角下直接 Gaussian rendering 可很差，因此改用提取的 mesh。其新采数据 reference poses 通过 hloc 和人工剔除得到；不能不加说明地称外部物理 ground truth。

**对研究定位的直接影响：** “confidence-aware geometry + virtual keyframes + localization” 本身已存在。GhostMap 的新贡献不能只把这几项组合换个校园场景。潜在研究差异应是跨世纪结构变化、证据相关性、独立曝光组、可校准的拒绝 / 不确定性等，但也必须继续检查这些方向已有文献，不预先宣布首创。

## 4. 现代 Arts Quad 的可执行使用顺序

1. **真实照片主线：** SIFT + COLMAP 做可重复基线；SuperPoint / ALIKED / DISK + LightGlue + COLMAP 做性能主线。检索候选图、邻接建筑 overlap、loop closure 都保留可审计记录。
2. **困难图对补救：** 在真实图对上测试 LoFTR / MASt3R 的 2D 匹配；对重复窗格做几何、cycle consistency、空间覆盖和多视图 track 验证。切换 matcher 不得只比较匹配点数量。
3. **几何地图：** 同一坐标系中完成 MVS depth、visibility、融合和分块表面，先验证 facade 和跨建筑连接，再渲染虚拟图。未连通组件不能靠排版或手动摆放成为共同地图。
4. **已验证网格的虚拟视图：** 先使用纯几何投影 / 照片贴图，不使用生成式补全。渲染 RGB、depth、normal、surface ID、source-view support、无数据 mask；只在观测支持区生成定位匹配。
5. **真实留出图定位：** 用真实照片作 queries，对比 real-only、real+virtual 和 virtual-only 的 recall / error / rejection。虚拟视图只能改善检索、表示及优化，不是额外独立测量。
6. **可选学习先验分支：** GPVK 类 depth / normal regularization、DUSt3R / VGGT 初始化等放在隔离分支；几何与来源标记为 prior-assisted。只有独立测试显示改进且不增大 confident false positives 才采用。
7. **历史阶段：** 保留上述现代基准。只用可信稳定环境作为跨时代锚点，再恢复历史独有部分；已拆除、被遮挡、未被真实照片观测的部分显示 unknown。

从深度提升匹配的形式为：给定参考相机 (K,R,t)、参考像素 (u)、相机 z-depth (z>0)，令 (X=R^T(zK^{-1}\bar u-t))。query 像素与该 (X) 构成定位约束。渲染 / undistortion 的坐标约定、像素缩放、depth 是 z 还是 ray distance 都必须有单元测试，否则数据看似匹配也可能产生错位。

## 5. 学习组件的实际能力与工程状态

以下以官方文档 / README 为核对层级，除上面的论文外，本节不宣称逐篇读完 PDF，也不宣称已在本项目新数据上运行。

| 组件 | 官方资料 | 能做什么 | 不能推导出的结论 |
|---|---|---|---|
| hloc | [代码](https://github.com/cvg/Hierarchical-Localization)；[CVPR 2019](https://arxiv.org/abs/1812.03506) | 模块化 retrieval、匹配、COLMAP mapping 和 query localization，保留 inlier / query 日志 | 成功注册不等于表面完整或物理正确 |
| LightGlue | [代码](https://github.com/cvg/LightGlue)；[ICCV 2023](https://arxiv.org/abs/2306.13643) | 已有 keypoints / descriptors 之间的高效 sparse matching | 匹配信心不等于几何误差概率 |
| LoFTR | [代码](https://github.com/zju3dv/LoFTR)；[CVPR 2021](https://arxiv.org/abs/2104.00680) | detector-free dense / semi-dense 图像对应，适合局部低纹理补救 | 不能辨认未观测区域的真实深度；重复结构仍可能误配 |
| DUSt3R | [代码](https://github.com/naver/dust3r)；[CVPR 2024](https://arxiv.org/abs/2312.14132) | 学习 pointmaps、confidence 与 pair/global alignment | 单 / 双视图 plausible 形状不是独立多视角测量 |
| MASt3R / MASt3R-SfM | [代码](https://github.com/naver/mast3r)；[ECCV 2024](https://arxiv.org/abs/2406.09756) | 增加 feature head、3D-grounded matching、metric pointmap、可扩展 alignment | learned metric scale 不是 survey 校准；官方自己称 COLMAP / GLOMAP bridge 为未广泛测试的 “toys” |
| VGGT | [代码](https://github.com/facebookresearch/vggt)；[CVPR 2025](https://arxiv.org/abs/2503.11651) | 前馈相机 / 内参、深度、pointmap、tracks，可导出 COLMAP 格式并可 BA | **导出 COLMAP 格式不等于由真实匹配独立验证的 COLMAP 结果** |

代码、checkpoint 和输入图像的许可分别审核。LightGlue 代码 / 权重是 Apache-2.0，但其支持的 SuperPoint 有不同限制；DUSt3R / MASt3R 官方 README 列 CC-BY-NC-SA 4.0，权重另涉及训练数据条款；VGGT 有 checkpoint-specific license 区别。最终公开网站、模型和复现包按实际选择做 manifest，不能把学术使用自动等同于可无限再分发。

## 6. 不产生“数据支持”假象的统计规则

### 数据依赖和循环验证

- 渲染视角 (V=\operatorname{render}(M,C)) 是已有模型 (M) 的函数。1000 个 (V) 不能算 1000 次独立观测，也不能用它们反过来证明 (M) 正确。
- 虚拟视图与新的真实 query 匹配时，新信息来自真实 query 像素；地图、纹理和虚拟图仍共享来源。报告 unique real images / exposure groups / supported surface，不把 virtual matches 累加为独立 support。
- 不能用某张查询照片建 MVS / 纹理 / radiance field，再把它作该方法的 held-out visual test。必要时为每个 split 重建训练地图。
- 同一底片的裁切、翻转、不同扫描、出版印刷 / 着色版本属于同一曝光组。互联网下载文件数不是视角数，重新扫描的几何畸变也不是视差。
- 已知目标 pose 处渲染的图只用于诊断 / image comparison，不可偷渡为真实未知 query 的 retrieval 输入。

### 分离观测支持、先验支持和未知

每个 surface element、camera hypothesis 和 match 要保存 `observed_real / derived_render / learned_prior / unknown` 类型及 dependency IDs。对直接观测几何再记录独立拍摄组、基线、可见性、depth agreement 和校准敏感度。证据类型和 confidence 是两个不同维度，不能用 confidence 分数掩盖先验来源。

### 不确定性不能只看 reprojection error

相机内参未知、扫描裁切、近共面立面、纯旋转、重复窗格、窄基线和错误组件连接都可能得到低重投影误差。除了 robust residual，还须做 focal / camera-model sensitivity、block bootstrap over exposure groups、跨独立 matcher / seed 一致性、多平面 / 深度覆盖和留出组表现。PnP 的条件协方差未包含地图和内参误差，不能直接当完整世界坐标不确定性。

没有独立 metric scale / ground truth 时，报告相对尺度稳定性和 relative error，不能承诺厘米级。由训练照片重建的 reference pose 应称 SfM reference / pseudo-reference，且注明共同方法带来的偏差。

## 7. 必做的实验矩阵与 go / no-go

| 实验 | 固定条件 | 关键比较 | 判定依据 |
|---|---|---|---|
| 真实特征基线 | 同一 admission / exposure-group split、retrieval budget、相机模型 | SIFT、LightGlue、LoFTR difficult-pair rescue、MASt3R matches | 正确连接与注册、holdout recall、空间支持、失败率、计算成本 |
| 虚拟视图 | 冻结且验证过的训练网格、相同 query set | real-only / real+virtual / virtual-only | 未见真实 query 的定位提升及 false-accept 风险，不能只看 inlier 数 |
| 网格质量依赖 | 相同 matcher / query / virtual camera budget | MVS mesh vs simplified mesh vs prior-assisted mesh | 定位误差、surface support、模型误差传播和 prior-induced false positives |
| 视角 / 时间外推 | split 在训练前冻结 | 新拍摄者、季节、背向视角、明显结构变化 | coverage、selective risk–coverage curve、拒绝是否可靠 |
| 数据依赖 | 同一真实信息量 | 单曝光多扫描 vs 多独立真实照片 | 避免点数 / 匹配数量膨胀造成虚假的 confidence |

现代 Cornell 结果缺少独立真实相机 ground truth 时，先在 Aachen / Cambridge / 有测量参考的合适公开 benchmark 测 solver 与 rejection，再在 Cornell 报来源隔离的 reference consistency；两者不能混成同一物理精度结论。最终 paper 若要对建筑绝对尺寸或厘米级误差作主张，需公开、可核实的测量参照，否则收窄结论。

**采用门槛：** 虚拟视图分支必须在固定的独立真实 query split 上提高可验证的定位覆盖，同时不恶化错误高信心接受；渲染区域有可靠观测支持，图像 / 几何 / 许可 provenance 可追溯。具体阈值由现代数据 pilot 冻结，不能看到测试结果后调阈值。

**拒绝条件：** 地图本身不稳定、需要凭空补建筑才能定位、没有足够稳定跨时代锚点、或改进只在重复扫描 / 测试泄漏下出现，则不把该分支作为成功结果。

## 8. 对长期项目的推荐结论

现代 Arts Quad 是可复用的证据地图，先完成真实数据覆盖、共同相机坐标系和高质量表面，再引入虚拟视图提升定位和交互。MeshLoc / InLoc 是第一组可解释、可复现基线；GPVK-VL 是必须承认的更强相关工作。人体 VC 用于理解“语义先验能在何处提供额外约束”，不作为对 Cornell 建筑自动有效的承诺。

PhD-level 价值需要在明确科学问题上证明改进，例如在结构变化且证据依赖严重时，如何可靠定位、如何知道恢复范围、如何校准拒绝与不确定性。精美交互页面是重要交付，但不是算法新颖性或几何真实性的替代品。
