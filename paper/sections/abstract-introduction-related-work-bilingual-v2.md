# MGA新版论文题目、摘要、引言与相关工作（中英双语）

> 版本：v2，2026-07-27  
> 目标：ACM MM 风格主稿的论证底稿  
> 方法定位：面向开放式遥感变化描述/变化回答的双时相证据关联评价框架  
> 结果口径：仅使用当前正式归档能够支持的结论，不把先导人工实验写成最终效度结论

---

## 0. 论文定位与写作主线

### 0.1 推荐题目

**中文：**

> **MGA：面向开放式遥感变化描述的混合证据关联评价框架**

**English:**

> **MGA: A Hybrid Evidence-Grounded Evaluation Framework for Open-Ended Remote Sensing Change Descriptions**

该题目相较初版题目 *The Alignment Paradox in Remote Sensing Change Captioning: Evaluating VLM Feedback with Mask-Guided Alignment* 做了两点收敛：

1. 将论文主语从“VLM feedback”改为“open-ended change description evaluation”，避免生成框架与评价方法争夺主贡献。
2. 保留“Alignment Paradox”作为引言中的动机性观察，而不再将其作为只能由 Teacher–Student 实验支撑的题目主张。

可选的更具传播性的题目为：

> **Beyond Text Similarity: Hybrid Evidence Grounding for Open-Ended Remote Sensing Change Description Evaluation**

### 0.2 技术主线

本文只围绕一条技术主线展开：

> **候选描述 → 原子变化 Claim → 双时相实体证据 → MGA-OV / MGA-GT / MGA-Hybrid 路由 → Spatial / Temporal / Coverage / Verifiability → Caption 级诊断结果**

其中：

- **MGA-Hybrid** 是主方法：标注体系内实体使用语义标签，标签外实体使用开放词汇视觉证据。
- **MGA-GT** 是理想证据上界：使用完整双时相语义标签验证类别转移和空间关系。
- **MGA-OV** 是开放实体证据压力测试：受控实验固定变化 ROI 以隔离实体 Grounder 的误差；No-ROI、RGB 特征差分 ROI 和预测变化图 ROI 证明其可脱离测试 GT 运行，但尚未稳定提升总体判别性能。
- **GTClassLookup / MaskLabelOnly** 是决定性简单基线：它只能查询标注类别是否出现，不能完整验证时相方向、标签外实体和细粒度空间关系。

### 0.3 初版稿件中保留与重构的内容

**保留：**

1. “文本相似度不等于图像事实正确性”的核心问题。
2. “Alignment Paradox”这一现象性观察：语义更丰富的描述可能获得更低文本分数，而流畅、近似参考的描述仍可能缺少视觉证据。
3. 实体级解析、时相感知定位和图像中心评价的基本思想。
4. MGA 是补充传统语言指标的事实诊断工具，而不是语言质量、流畅度和信息完整性的全能总分。

**重构或删除：**

1. Teacher–Student feedback 不再作为方法主线，只可作为开放式描述产生新事实与幻觉风险的动机案例。
2. 删除“changed/context 两项以固定 0.7/0.3 权重组成唯一 MGA Score”的核心定义，改为优先报告分量向量。
3. 不再笼统宣称 MGA “reference-free”。更准确的表述是：MGA 不依赖参考句文本，但不同模式可能依赖语义标签或开放视觉模型。
4. 不再使用单一 GroundingDINO/SAM 结果代表完整双时相事实；新版显式区分 Add、Remove、Modify、关系证据和不可验证状态。
5. 不再以 Draft、Guided 和 Change-Agent 的平均 MGA 排名作为主要有效性证据，改用事实图驱动的受控样本、路由消融、人工效度和失败类型分析。

### 0.4 新版方法贡献

1. **问题与表示贡献。** 将开放式遥感变化语言的评价定义为原子声明与双时相图像证据之间的关联问题，并分别报告实体空间支持、变化方向、事实覆盖和不可验证性。
2. **方法贡献。** 提出逐实体的 Hybrid 证据路由，在可靠的封闭语义标签和可扩展的开放词汇视觉证据之间选择后端，并以 MGA-GT 和 MGA-OV 给出理想上界与开放条件压力测试。
3. **评价协议贡献。** 从双时相语义标签构建事实图，并生成事实描述、最小事实矛盾和语义保持改写三类样本，同时考察错误敏感性与改写鲁棒性。
4. **实证贡献。** 通过简单类别查找、开放词汇证据、Hybrid 和全类别 Oracle 的对照，量化标签覆盖、Parser 和开放分割误差如何传播到最终评价，并结合三评审先导实验说明分量式报告的必要性。

---

# 中文稿

## 摘要的七段式逻辑

1. **任务：** 评价开放式遥感变化描述是否正确表达双时相图像中的地表变化。
2. **问题：** 参考文本指标主要衡量候选句与有限参考句是否相似，不能直接验证实体、时相方向与空间位置是否得到图像支持。
3. **思路：** 将评价目标从文本相似度转换为原子变化 Claim 与双时相视觉证据之间的关联。
4. **难点：** 双时相变化关系比单图实体存在更复杂，同时语义标签类别有限、开放词汇分割存在噪声。
5. **方法：** 用 Parser 和同义词规范化提取 Claim，通过 MGA-GT、MGA-OV 与逐实体 MGA-Hybrid 路由构造证据，再输出 Spatial、Temporal、Coverage 和 Verifiability。
6. **结果：** Hybrid 在 SECOND-CC 受控基准上显著优于纯开放词汇证据，并在隐藏类别条件下避免简单 GT 查找的覆盖率崩塌。
7. **意义：** MGA 为变化描述与变化问答提供了参考文本指标之外的、可解释且能定位失败原因的事实评价协议。

## 摘要

开放式遥感变化描述旨在用自然语言概括双时相影像中发生的地表变化，其可靠评价是比较和改进变化描述模型的基础。现有协议主要依赖 BLEU、CIDEr、METEOR、ROUGE-L 和 SPICE 等参考文本指标，因而难以区分语义保持改写与事实错误，也无法直接判断描述中的实体、变化方向和空间位置是否得到图像支持。为此，本文提出 Mask-Guided Alignment（MGA），将评价目标从“候选句是否类似参考句”转换为“原子变化声明是否能够在双时相图像中找到一致证据”。这一思路面临两个相互关联的困难：实体存在并不等于发生了新增、移除或修改，而真实数据中的语义标签通常只覆盖少量类别，开放词汇视觉模型又会引入定位噪声。MGA 首先通过领域 Parser 和同义词规范化将文本分解为原子 Claim，随后以 MGA-GT、MGA-OV 和逐实体 MGA-Hybrid 三种模式路由双时相实体掩膜，并分别输出空间支持、时相支持、事实覆盖和不可验证率，而不把所有误差强行压缩为未经校准的单一总分。在由 200 个 SECOND-CC 场景构建的 600 条受控评价样本上，MGA-Hybrid 在闭集条件下取得 0.944 ROC-AUC，明显高于 MGA-OV 实体证据基线的 0.580；在隐藏类别条件下，Hybrid 保持完整覆盖并取得 0.711 ROC-AUC，而简单 GT 类别查找仅覆盖 19.5% 的样本。结果表明，MGA-Hybrid 能够在可靠标注与开放视觉证据之间取得更合理的覆盖—精度折中，为开放式遥感变化描述和变化问答提供一种可解释、可扩展且以图像事实为中心的评价协议。

## 1 引言

双时相遥感影像记录了城市扩张、道路建设、植被演替、水体变化和灾害影响等地表过程。遥感变化描述（remote sensing change captioning, RSCC）和变化视觉问答进一步将这些变化转换为自然语言，使系统能够回答“什么发生了变化、如何变化以及变化位于何处”。随着 Transformer、视觉语言模型和多模态大模型被引入这一任务，模型输出正在从短句模板走向包含更多实体、属性和空间关系的开放式描述 [Liu et al., 2022; Chang and Ghamisi, 2023; Liu et al., 2024a; Zhu et al., 2025]。生成能力的提升也改变了评价问题：当前的关键不再只是句子是否流畅或是否接近参考措辞，而是其中声明的变化能否由双时相图像事实支持。

现有 RSCC 研究仍主要使用 BLEU、METEOR、ROUGE-L、CIDEr 和 SPICE 衡量候选句与人工参考句的相似程度。该协议便于复现，却隐含假设“越接近有限参考句，描述越正确”。然而，同一地表变化可以通过不同词汇、句法和粒度表达，参考句也不可能穷举图像中的全部事实。由此产生了初版工作所观察到的 **Alignment Paradox**：语义保持但措辞不同的描述可能因词汇重叠下降而被惩罚，而一条流畅、接近参考风格的句子仍可能虚构实体、颠倒新增与移除方向，或将变化定位到错误区域。换言之，文本指标衡量的是“候选句与参考句有多像”，却不能单独回答“候选句是否符合图像”。

通用图像描述评价已经开始引入图文对齐、对象幻觉检测和大模型语义判断。TIGEr 使用图文 grounding 表示比较候选描述，InfoMetIC 输出文本精确性、视觉召回和细粒度错误，ALOHa 结合实体抽取、参考对象和检测对象识别开放词汇幻觉 [Jiang et al., 2019; Hu et al., 2023; Petryk et al., 2024]。在遥感领域，FMScore 将变化描述与事实集合匹配，ReconScore 根据文本重建图像并衡量视觉一致性 [Ricci et al., 2026; Chen et al., 2026]。这些工作共同推动评价从表面文本匹配转向视觉或事实一致性，但不能直接解决 RSCC 的全部要求：多数通用指标面向单幅自然图像，FMScore 主要验证文本与事实集合的匹配，ReconScore 面向单图场景重建；它们均未显式检验一个实体是否在正确时相、正确位置形成了所声明的变化关系。

面向开放式 RSCC 的证据评价具有三项核心挑战。第一，双时相关系不可约化为单图实体存在：在两幅图中都能找到 building，并不能证明它是新增建筑；同理，描述 source 被 target 替代时，还需要验证二者是否在相同变化区域形成 remove→add 关系。第二，语义标签提供精确但封闭的类别证据。建筑、道路等标注类别可以直接核验，但树木、河流或其他真实地物可能不在标签体系内，将其一律视为幻觉会系统性惩罚更丰富的正确描述。第三，开放词汇分割虽然能够查询标签外实体，却受到类别混淆、过分割、配准误差和置信度校准的影响；检索失败并不必然意味着文本错误。因此，一个可靠评价器必须同时区分“证据支持”“证据反驳”和“当前证据不足”。

为此，本文提出 Mask-Guided Alignment（MGA），一种面向开放式遥感变化描述与变化回答的双时相证据关联评价框架。MGA 首先利用领域词表、同义词规范化和回退式轻量实体抽取，将候选文本分解为 `(entity, change, location, role, attributes)` 形式的原子 Claim。随后，评价器为每个实体构造 T1/T2 掩膜，并根据 Add、Remove 和 Modify 形成时相差分与空间关系证据。为适应不同标注条件，我们定义三个统一模式：MGA-GT 使用完整双时相语义标签，表示理想证据上界；MGA-OV 使用开放词汇实体证据，作为视觉后端压力测试；主方法 MGA-Hybrid 则按实体路由，标注类别使用 GT，标签外类别使用开放词汇掩膜。受控实验使用固定变化 ROI 以隔离实体 Grounder 误差；同时，我们补充了 No-ROI、RGB 特征差分 ROI 和预测变化图 ROI 三种无测试 GT 配置。它们证明 MGA-OV 可以脱离测试语义标签运行，但当前并未稳定提升总体 AUC，因此 MGA-OV 仍应被表述为开放视觉后端压力测试，而非已经成熟的完全无标注评价器。三种模式共享同一验证器，并输出 Spatial Support、Temporal Support、Coverage、Context Support 和 Unverifiable Rate。该分量式设计使分割失败、标签缺失和文本矛盾不再被混入同一个不可解释分数。

我们从 SECOND-CC 的双时相语义标签构建像素级事实图，并针对 200 个场景生成事实描述、仅替换目标实体的最小矛盾描述和保持事实不变的语义改写，共得到 600 条受控评价样本。该协议同时检验指标对事实错误的敏感性和对措辞变化的鲁棒性。闭集实验中，MGA-Hybrid 获得 0.944 ROC-AUC 和 0.935 balanced accuracy，接近全类别 Oracle 的 0.958，并显著高于 MGA-OV 实体证据基线的 0.580 ROC-AUC。在隐藏 tree、low vegetation 和 water 后，简单 GT 类别查找的覆盖率降至 19.5%，而 Hybrid 保持完整覆盖并取得 0.711 ROC-AUC，较纯开放词汇证据提升 0.131，场景级 bootstrap 置信区间不跨 0。三评审 50 场景先导实验进一步表明，时相支持是当前最具判别力的单一视觉分量，而未经独立校准的 Overall 不应承担主要结论。这些结果支持以 Hybrid 为主方法、GT 为上界、OV 为压力测试，并优先报告可解释分量而非唯一总分。

本文的主要贡献如下：

1. 提出一个面向双时相遥感语言输出的原子 Claim 评价框架，将实体类别、时相方向、空间关系、事实覆盖和不可验证性分别建模，从而补充只关注参考文本相似度的传统协议。
2. 提出逐实体 Hybrid 证据路由，并以 MGA-GT、MGA-OV 和 MGA-Hybrid 统一描述完整标注、开放证据和部分标注三种使用条件。
3. 提出基于双时相语义事实图的受控评价协议，通过事实描述、最小事实矛盾和语义保持改写同时检验指标的错误敏感性与改写鲁棒性。
4. 在 LEVIR-MCI 人工先导集和 SECOND-CC 多类别受控基准上系统分析 Parser、标签覆盖和开放词汇分割的误差传播，验证 Hybrid 的覆盖—精度优势，并明确当前方法的适用边界。

## 2 相关工作

### 2.1 遥感变化描述与变化问答

早期 RSCC 方法通常采用双分支编码器提取前后时相特征，并通过循环网络或 Transformer 解码变化描述。LEVIR-CC/RSICCformer 建立了大规模双时相变化描述基准，Chg2Cap 通过跨时相注意力增强变化表征 [Liu et al., 2022; Chang and Ghamisi, 2023]。后续研究逐渐引入像素级变化先验、基础视觉模型和多模态大模型：Semantic-CC 使用语义变化信息指导描述生成，Change-Agent 将变化检测、描述和问答组织为交互式解释系统，Change3D 则从视频建模角度统一变化检测与变化描述 [Liu et al., 2024a; Liu et al., 2024b; Zhu et al., 2025]。与固定描述互补，CDVQA 等数据集以问题—回答形式查询双时相变化，进一步扩大了开放变化语言的输出空间。

SECOND-CC 对本文尤为重要。该数据集在变化描述之外提供双时相语义图，使同一场景同时具备自然语言参考和多类别像素转移事实 [Karaca et al., 2025]。这为检验“类别查找是否因标签空间过窄而被高估”以及构造实体替换型最小矛盾样本提供了条件。然而，SECOND-CC 和大多数 RSCC 工作的目标仍是改进生成器，主要评价协议依然是 BLEU、CIDEr、METEOR、ROUGE-L 和 SPICE。本文不提出新的描述生成器，而是研究如何将双时相语义与开放视觉证据转化为可解释的语言事实核验。

### 2.2 图像描述的文本、语义与事实评价

BLEU、METEOR、ROUGE、CIDEr 和 SPICE 分别从 n-gram、词语匹配或场景图结构比较候选文本与人工参考。它们在固定基准上具有良好可复现性，但有限参考无法覆盖图像中的全部合法描述，分数还会受到句式、长度和标注风格影响。近期对七十余种图像描述指标的系统调查也表明，研究仍高度依赖少数传统指标，而这些指标与人工判断的相关性有限 [Berger et al., 2025]。因此，MGA 并不主张删除文本指标，而是将其解释为语言/参考一致性维度，并补充独立的图像事实维度。

图像中心指标尝试缓解参考文本偏差。TIGEr 通过文本—图像 grounding 评价候选描述；UMIC、CLIPScore 和 PAC-S 等方法直接建模图文一致性；InfoMetIC 进一步报告不准确词语、遗漏区域、文本精确性和视觉召回 [Jiang et al., 2019; Hu et al., 2023]。然而，参考无关指标在细粒度语义扰动、对象大小和表达变化下仍可能不稳定 [Ahmadi and Agrawal, 2024]。更重要的是，单图图文对齐只验证对象或场景是否存在，无法判断对象在 T1 和 T2 之间的新增、移除或类别转换。

事实性和幻觉评价更接近本文目标。ALOHa 使用 LLM 提取可定位对象，并将其与参考对象和检测结果匹配，从而扩展到开放词汇幻觉 [Petryk et al., 2024]。遥感领域的 FMScore 使用 LLM 比较候选描述与预定义变化事实，ReconScore 则通过文本到图像的重建质量评价单图遥感描述 [Ricci et al., 2026; Chen et al., 2026]。MGA 与这些工作共享“超越文本表面相似度”的目标，但研究对象不同：MGA 将变化句拆解为实体—方向—位置 Claim，并要求其在双时相像素证据中形成可追踪关系。因此，MGA 既不等同于事实列表匹配，也不等同于单图图文相似度。

### 2.3 开放词汇遥感分割与变化检测

开放词汇遥感分割为标签体系之外的实体提供了像素级查询能力。SegEarth-OV 利用训练无关的特征恢复和偏差抑制改善遥感开放词汇分割，SegEarth-OV3 进一步探索基于 SAM 3 的语义/实例掩膜融合和存在性过滤 [Li et al., 2025a; Li et al., 2025b]。这些模型使 building、road、tree、water 等文本能够直接产生区域证据，但模型输出仍受类别相似性、密集小目标和遥感域差异影响。在本文的 SECOND-CC 诊断中，building 的时相差分相对稳定，而 tree、low vegetation、non-vegetated ground 和 playground 的混淆显著，说明开放分割结果不能被直接视为评价真值。

开放词汇变化检测进一步显式建模双时相差异。Semantic-CD 将 CLIP 语义先验与二值/语义变化解码结合，Seg2Change 使用类别无关变化头将开放词汇分割适配到变化检测，OpenDPR 则把任务拆分为类别无关变化提议和开放类别识别，并指出细粒度类别识别是主要瓶颈 [Zhu et al., 2025; Su et al., 2026; Guo et al., 2026]。这些工作优化的是变化区域与类别识别本身，而 MGA 研究的是如何将其作为语言评价证据，以及视觉后端失败时评价器应输出“矛盾”还是“不可验证”。因此，开放词汇模型在 MGA 中是可替换的证据后端，而非被假定为无误的裁判。

### 2.4 本文定位

本文位于变化语言评价、双时相视觉理解和开放词汇定位的交叉点。与参考文本指标相比，MGA 直接查询图像证据；与单图 grounding 指标相比，MGA 显式建模 Add、Remove、Modify 和 source→target 关系；与 FMScore 等事实匹配方法相比，MGA 将事实进一步绑定到双时相像素区域；与开放词汇变化检测相比，MGA 的目标不是提高分割精度，而是将标签覆盖、定位置信度和证据缺失传播为可解释的评价输出。其核心贡献不是某一个更强的视觉后端，而是一个能够比较 MGA-GT、MGA-OV 与 MGA-Hybrid，并区分 Supported、Contradicted 和 Unverifiable 的统一评价框架。

---

# English Draft

## Seven-Part Abstract Logic

1. **Task:** evaluate whether an open-ended remote sensing change description faithfully represents the changes in a bi-temporal image pair.
2. **Limitation:** reference-based metrics measure similarity to a small set of reference sentences rather than direct support from the images.
3. **Insight:** reformulate evaluation as grounding atomic change claims in bi-temporal visual evidence.
4. **Challenges:** temporal relations are more complex than single-image object presence, semantic labels are incomplete, and open-vocabulary masks are noisy.
5. **Method:** parse claims, route entity evidence through MGA-GT, MGA-OV, or entity-wise MGA-Hybrid, and report decomposed evidence dimensions.
6. **Results:** Hybrid substantially outperforms open-vocabulary-only evidence and avoids the coverage collapse of GT lookup under hidden classes.
7. **Impact:** provide an interpretable image-centered evaluation protocol for change captioning and change question answering.

## Abstract

Open-ended remote sensing change description aims to summarize land-cover changes in bi-temporal imagery with natural language, making reliable evaluation essential for comparing and improving generation systems. Existing protocols remain dominated by reference-based metrics such as BLEU, CIDEr, METEOR, ROUGE-L, and SPICE, which cannot reliably distinguish claim-preserving paraphrases from factual errors or directly verify whether the mentioned entities, temporal directions, and locations are supported by the images. We therefore propose Mask-Guided Alignment (MGA), which reformulates evaluation from measuring resemblance to reference sentences into grounding atomic change claims in bi-temporal visual evidence. This formulation introduces two coupled challenges: object presence alone does not establish addition, removal, or modification, while semantic annotations cover only a limited set of classes and open-vocabulary vision models introduce localization noise. MGA addresses these challenges by parsing a description into normalized atomic claims, routing bi-temporal entity masks through MGA-GT, MGA-OV, or an entity-wise MGA-Hybrid, and reporting spatial support, temporal support, fact coverage, and unverifiability instead of collapsing all errors into an uncalibrated scalar. On a controlled benchmark of 600 descriptions constructed from 200 SECOND-CC scenes, MGA-Hybrid achieves a ROC-AUC of 0.944 in the closed-set setting, substantially outperforming the MGA-OV entity-evidence baseline at 0.580; when several classes are hidden, Hybrid preserves full coverage and reaches 0.711 ROC-AUC, whereas direct GT class lookup covers only 19.5% of the samples. These results show that hybrid evidence routing offers a more effective coverage-accuracy trade-off between reliable annotations and extensible open-vocabulary evidence, providing an interpretable and image-centered evaluation protocol for open-ended remote sensing change captioning and change question answering.

## 1 Introduction

Bi-temporal remote sensing imagery records surface processes such as urban expansion, road construction, vegetation succession, water-body variation, and disaster impacts. Remote sensing change captioning (RSCC) and change-oriented visual question answering translate these observations into language that explains what changed, how it changed, and where the change occurred. With the introduction of Transformers, vision-language models, and multimodal large language models, RSCC outputs are evolving from short templates toward open-ended descriptions containing richer entities, attributes, and spatial relations [Liu et al., 2022; Chang and Ghamisi, 2023; Liu et al., 2024a; Zhu et al., 2025]. This increased generation capacity changes the evaluation target: the central question is no longer only whether a sentence is fluent or resembles a reference, but whether its change claims are supported by the bi-temporal observations.

Most RSCC studies continue to report BLEU, METEOR, ROUGE-L, CIDEr, and SPICE, all of which primarily measure similarity between a candidate and human-written references. Although this protocol is reproducible, it implicitly treats proximity to a limited set of references as a proxy for correctness. The same surface change, however, can be expressed with different words, syntactic structures, and levels of detail, while a few references cannot enumerate every valid fact in the images. This creates the **alignment paradox** observed in our initial study: a claim-preserving but lexically different description may be penalized, whereas a fluent sentence close to the reference style may still hallucinate an entity, reverse an addition into a removal, or localize the change in the wrong region. Reference similarity answers how much two sentences look alike; by itself, it does not establish whether the candidate agrees with the images.

General image-caption evaluation has increasingly incorporated image-text alignment, hallucination detection, and model-based semantic judgment. TIGEr evaluates captions through learned text-image grounding, InfoMetIC reports text precision, vision recall, and fine-grained errors, and ALOHa combines entity extraction with reference objects and detections to identify open-vocabulary hallucinations [Jiang et al., 2019; Hu et al., 2023; Petryk et al., 2024]. Remote sensing studies have also proposed FMScore, which matches change descriptions against fact sets, and ReconScore, which evaluates a single-image caption through visual reconstruction [Ricci et al., 2026; Chen et al., 2026]. These advances collectively move evaluation beyond surface overlap, but they do not fully capture the structure of RSCC. Most grounded metrics assume one static natural image, FMScore primarily evaluates text-to-fact matching, and ReconScore targets single-image scene reconstruction; none explicitly asks whether an entity forms the claimed transition at the correct time and location.

Evidence-grounded evaluation for open-ended RSCC is challenging for three reasons. First, a bi-temporal relation cannot be reduced to object presence: detecting a building in both images does not prove that a building was added, and a source-to-target replacement additionally requires removal and addition evidence to co-occur within the same change region. Second, semantic annotations offer accurate but closed-set evidence. Buildings and roads may be directly verifiable, whereas trees, rivers, and other valid objects may fall outside the label space; treating every unannotated entity as a hallucination systematically penalizes informative captions. Third, open-vocabulary segmentation can retrieve entities beyond the annotation vocabulary but is affected by class confusion, over-segmentation, registration errors, and confidence calibration. A grounding failure is therefore not equivalent to a textual contradiction. A useful evaluator must distinguish supported claims, contradicted claims, and claims for which the available evidence is insufficient.

We address this problem with Mask-Guided Alignment (MGA), a bi-temporal evidence-grounded evaluation framework for open-ended change descriptions and answers. MGA first uses a domain ontology, synonym normalization, and a fallback lightweight entity extractor to decompose a candidate into atomic claims of the form `(entity, change, location, role, attributes)`. It then constructs entity masks for T1 and T2 and derives temporal difference and spatial relation evidence for Add, Remove, and Modify claims. To support different annotation regimes, we define three modes under a shared verifier. MGA-GT uses complete bi-temporal semantic labels and represents an ideal evidence upper bound; MGA-OV uses open-vocabulary entity evidence as a visual-backend stress test; and the proposed MGA-Hybrid performs entity-wise routing, using semantic labels for annotated classes and open-vocabulary masks for unannotated entities. The controlled experiment holds the change ROI fixed to isolate entity-grounding errors; we additionally evaluate No-ROI, RGB feature-difference ROI, and predicted change-map ROI configurations that require no test-time semantic annotation. These variants establish that MGA-OV can run without test GT, but they do not consistently improve overall AUC, so MGA-OV remains a stress test rather than a mature annotation-free evaluator. Rather than forcing heterogeneous errors into a single score, MGA reports Spatial Support, Temporal Support, Coverage, Context Support, and Unverifiable Rate.

We construct pixel-level fact graphs from the bi-temporal semantic labels of SECOND-CC and create three controlled descriptions for each of 200 scenes: a factual statement, a minimally contradicted statement obtained by replacing the target entity, and a claim-preserving paraphrase. This design evaluates both sensitivity to factual errors and robustness to linguistic variation. In the closed-set setting, MGA-Hybrid obtains 0.944 ROC-AUC and 0.935 balanced accuracy, approaching the full-label oracle at 0.958 ROC-AUC and substantially outperforming the MGA-OV entity-evidence baseline at 0.580. When `tree`, `low vegetation`, and `water` are hidden, direct GT class lookup covers only 19.5% of the samples, whereas Hybrid retains full coverage and achieves 0.711 ROC-AUC, an improvement of 0.131 over open-vocabulary-only evidence with a scene-level bootstrap interval that does not cross zero. A three-rater pilot on 50 LEVIR-MCI scenes further indicates that temporal support is the most discriminative individual visual component, while an independently uncalibrated Overall score should not carry the main conclusion. Together, these findings support Hybrid as the practical method, GT as an upper bound, OV as a stress test, and decomposed evidence dimensions as the primary reporting protocol.

Our contributions are fourfold:

1. We formulate open-ended bi-temporal language evaluation as atomic claim grounding and separately model entity support, temporal direction, spatial relation, fact coverage, and unverifiability, complementing reference-based text similarity.
2. We introduce entity-wise hybrid evidence routing and unify complete-label, open-evidence, and partially annotated settings through MGA-GT, MGA-OV, and MGA-Hybrid.
3. We develop a fact-graph-based controlled evaluation protocol that jointly tests factual-error sensitivity with minimally contradicted descriptions and paraphrase robustness with claim-preserving rewrites.
4. We systematically analyze how parsing, label coverage, and open-vocabulary segmentation errors propagate into the final evaluation on a LEVIR-MCI human-evaluation pilot and a multi-class SECOND-CC benchmark, demonstrating the coverage-accuracy advantage and current limitations of hybrid evidence.

## 2 Related Work

### 2.1 Remote Sensing Change Captioning and Change Question Answering

Early RSCC methods typically used dual-stream encoders to extract pre- and post-event features and recurrent or Transformer decoders to generate change descriptions. LEVIR-CC/RSICCformer established a large-scale bi-temporal captioning benchmark, while Chg2Cap strengthened change representations through cross-temporal attention [Liu et al., 2022; Chang and Ghamisi, 2023]. Later studies increasingly incorporated pixel-level change priors, visual foundation models, and multimodal language models. Semantic-CC uses semantic change information to guide caption generation, Change-Agent organizes change detection, captioning, and question answering into an interactive interpretation system, and Change3D revisits change detection and captioning from a video-modeling perspective [Liu et al., 2024a; Liu et al., 2024b; Zhu et al., 2025]. Complementary benchmarks such as CDVQA query bi-temporal changes through questions and answers, further broadening the output space beyond a fixed caption.

SECOND-CC is particularly relevant to this work because it provides semantic maps together with multiple natural-language descriptions for bi-temporal image pairs [Karaca et al., 2025]. Its multi-class semantic transitions make it possible to examine whether simple class lookup is overestimated in narrow label spaces and to construct minimally contradicted descriptions by modifying individual entities. Nevertheless, SECOND-CC and most existing RSCC studies focus on improving generation models and continue to rely on BLEU, CIDEr, METEOR, ROUGE-L, and SPICE as the primary evaluation protocol. Our work does not introduce another caption generator; it studies how bi-temporal semantic and open-vocabulary visual evidence can be converted into an interpretable verifier for generated language.

### 2.2 Textual, Semantic, and Factual Caption Evaluation

BLEU, METEOR, ROUGE, CIDEr, and SPICE compare candidate descriptions with human references through n-grams, token matching, or scene-graph structures. They remain useful for reproducible benchmarking, but a limited reference set cannot cover all valid descriptions, and scores are affected by syntax, length, and annotation style. A recent survey of more than seventy captioning metrics further shows that the field still relies heavily on a small set of conventional metrics that correlate only weakly with human ratings [Berger et al., 2025]. MGA therefore does not replace textual metrics; it treats them as measures of linguistic or reference agreement and adds an independent image-evidence dimension.

Image-centered metrics reduce dependence on reference wording. TIGEr evaluates captions through text-image grounding; UMIC, CLIPScore, and PAC-S directly model image-text compatibility; and InfoMetIC identifies inaccurate words and omitted regions while reporting text precision and vision recall [Jiang et al., 2019; Hu et al., 2023]. Nevertheless, reference-free metrics may remain sensitive to fine-grained semantic perturbations, object size, and benign linguistic variations [Ahmadi and Agrawal, 2024]. More importantly for RSCC, single-image alignment can confirm that an object is visible without determining whether it was added, removed, or transformed between two observations.

Factuality and hallucination metrics are more closely related to our goal. ALOHa extracts groundable objects with an LLM and matches them to reference objects and detections, enabling open-vocabulary hallucination measurement [Petryk et al., 2024]. In remote sensing, FMScore compares a candidate change description with predefined facts through an LLM, while ReconScore evaluates a single-image caption according to the quality of text-conditioned visual reconstruction [Ricci et al., 2026; Chen et al., 2026]. MGA shares their motivation to move beyond surface text similarity but differs in its verification unit and evidence: it decomposes a change sentence into entity-direction-location claims and requires each claim to form a traceable relation in bi-temporal pixel evidence. It is therefore neither a fact-list matcher nor a single-image similarity metric.

### 2.3 Open-Vocabulary Remote Sensing Segmentation and Change Detection

Open-vocabulary remote sensing segmentation offers pixel-level evidence for entities outside a dataset's annotation vocabulary. SegEarth-OV improves training-free open-vocabulary segmentation through feature recovery and bias suppression, while SegEarth-OV3 explores semantic-instance mask fusion and presence filtering with SAM 3 [Li et al., 2025a; Li et al., 2025b]. These models make it possible to query textual categories such as buildings, roads, trees, and water, but their masks remain affected by semantically similar classes, dense small objects, and remote sensing domain shifts. Our SECOND-CC diagnostics show that buildings are comparatively stable, whereas trees, low vegetation, non-vegetated ground, and playgrounds exhibit substantial confusion. Open-vocabulary masks should therefore be treated as uncertain evidence rather than evaluation ground truth.

Open-vocabulary change detection further models temporal differences explicitly. Semantic-CD combines CLIP semantic priors with binary and semantic change decoders, Seg2Change adapts open-vocabulary segmenters through a category-agnostic change head, and OpenDPR decomposes the problem into class-agnostic change proposals and open-category identification, identifying fine-grained category recognition as a major bottleneck [Zhu et al., 2025; Su et al., 2026; Guo et al., 2026]. These approaches optimize change localization and recognition, whereas MGA studies how such predictions should support language evaluation and whether a failed visual query warrants contradiction or unverifiability. Open-vocabulary models are replaceable evidence backends in MGA, not assumed-perfect judges.

### 2.4 Positioning of This Work

This work lies at the intersection of change-language evaluation, bi-temporal visual understanding, and open-vocabulary localization. Compared with reference-based metrics, MGA queries visual evidence directly. Compared with single-image grounding metrics, it explicitly models Add, Remove, Modify, and source-to-target transitions. Compared with fact-matching approaches such as FMScore, it binds textual facts to bi-temporal pixel regions. Compared with open-vocabulary change detection, its goal is not to improve segmentation accuracy but to propagate label coverage, grounding confidence, and missing evidence into interpretable evaluation outcomes. The primary contribution is thus not a particular visual backbone, but a unified framework that compares MGA-GT, MGA-OV, and MGA-Hybrid and distinguishes Supported, Contradicted, and Unverifiable claims.

---

## 3 反向提纲

### 摘要

- 任务：开放式双时相变化语言评价。
- 缺口：参考文本相似度不能验证图像事实。
- 洞见：把评价改写为原子 Claim 与双时相证据的关联。
- 难点：时相关系、标签不完备、开放视觉噪声。
- 方法：三模式证据路由与分量式输出。
- 证据：SECOND-CC 200 场景受控实验。
- 意义：面向变化描述和变化问答的可解释评价协议。

### 引言段落功能

1. 定义任务、开放语言趋势和新的评价目标。
2. 解释文本指标的结构性错位与 Alignment Paradox。
3. 说明通用图文/事实指标的进展及其双时相缺口。
4. 分解三个技术挑战。
5. 给出 MGA 技术主线和三模式。
6. 给出评价协议、主要结果及证据边界。
7. 总结四项贡献。

### 相关工作分组

1. 遥感变化描述与变化问答。
2. 文本、图文与事实性描述评价。
3. 开放词汇遥感分割与变化检测。
4. 本文在三条研究线交叉处的技术定位。

---

## 4 主张—证据映射

| Claim | Evidence | Status |
|---|---|---|
| 参考文本相似度不能充分验证开放式变化事实 | 文献分析；事实描述/语义改写/最小矛盾协议；初版 Alignment Paradox 案例 | supported，但正式主表仍需加入 BLEU/CIDEr/CLIPScore 等对照 |
| Hybrid 在闭集条件下优于 OpenVocabOnly | SECOND-CC 200 场景：AUC 0.944 vs. 0.580；差值 bootstrap 区间不跨 0 | supported |
| Hybrid 能缓解标签隐藏导致的覆盖率崩塌 | hidden-class：Hybrid coverage 1.000；GTClassLookup coverage 0.195 | supported |
| Hybrid 已获得充分的人类效度 | 当前仅有 50 场景、3 评审先导实验，且 Overall AUC 不稳定 | needs evidence，不应在摘要中宣称 |
| Temporal 是有价值的独立证据 | 三评审先导集：Temporal AUC 0.782，balanced accuracy 0.739 | supported as pilot |
| MGA 对真实模型开放式输出总体优于所有现有指标 | 尚缺真实多模型输出上的完整指标相关性、pairwise ranking 和显著性 | needs evidence |
| MGA-OV 可以不使用测试 GT 运行 | No-ROI、RGB 特征差分 ROI 与预测变化图 ROI 均已实现；但 AUC 未稳定优于 No-ROI | 部分支持；只能主张可运行，不能主张已解决无标注可靠性 |

---

## 5 审稿人式自检

### 贡献

- **Pass：** 主问题已从“反馈生成 + 新指标”收敛为一个评价问题。
- **Pass：** Hybrid 路由、三模式统一定义和受控事实协议形成明确方法主线。
- **Pass with caveats：** 已完成 ALOHa-local、FMScore-Qwen、传统文本指标及 CLIP 双时相对照；复现实现与原论文默认模型不同，需在正文中透明标注，不能宣称全面优于所有强基线。

### 写作清晰度

- **Pass：** MGA-GT、MGA-OV、MGA-Hybrid 的角色已稳定。
- **Pass：** 不再混用 “reference-free” 与 “annotation-free”，并明确无测试 GT 配置的当前性能边界。
- **Needs revision：** 最终 LaTeX 需要统一 `change description`、`change captioning`、`claim`、`fact graph` 和 `evidence route` 的大小写与缩写。

### 实验强度

- **Pass：** SECOND-CC 200 场景结果和 bootstrap 区间能够支撑 Hybrid 的机制性结论。
- **Needs new experiment：** 需要多个真实生成模型输出，而不仅是受控三类文本。
- **Needs new experiment：** 建议在独立验证集校准阈值，并在 held-out 集上固定报告。

### 评价完整性

- **Pass：** 已包含 GTClassLookup、OpenVocabOnly、Hybrid 和 Oracle。
- **Needs new experiment：** 增加传统文本指标、通用图文指标和事实指标与人工判断的 Spearman/Kendall、pairwise accuracy。
- **Needs new experiment：** 增加类别隐藏比例曲线、长尾类别宏平均与 Parser 开放表达压力测试。

### 方法合理性

- **Pass：** 不把开放词汇分割失败直接解释为文本矛盾。
- **Pass：** 不把未经验证的 Overall 作为唯一结论。
- **Needs revision：** 真正的 MGA-OV 必须使用图像生成的变化 ROI，或明确将当前设置命名为 `OV-entity + GT-change-ROI`。

---

## 6 需要统一到 BibTeX 的主要文献入口

1. Liu et al., 2022, *Remote Sensing Image Change Captioning with Dual-Branch Transformers*.
2. Chang and Ghamisi, 2023, *Changes to Captions*.
3. Liu et al., 2024, *Change-Agent*.
4. Liu et al., 2024, *Semantic-CC*.
5. Zhu et al., 2025, *Change3D*.
6. Karaca et al., 2025, *SECOND-CC Dataset and MModalCC*.
7. Jiang et al., 2019, *TIGEr*.
8. Hu et al., 2023, *InfoMetIC*.
9. Petryk et al., 2024, *ALOHa*.
10. Berger et al., 2025, *Surveying the Landscape of Image Captioning Evaluation*.
11. Ahmadi and Agrawal, 2024, *Robustness of Reference-Free Image Captioning Evaluation Metrics*.
12. Ricci, Bazi, and Melgani, 2026, *Remote Sensing Change Captioning Meets Large Language and Vision Models*.
13. Chen et al., 2026, *Evaluating Remote Sensing Image Captions Beyond Metric Biases*.
14. Li et al., 2025, *SegEarth-OV* and *SegEarth-OV3*.
15. Zhu et al., 2025, *Semantic-CD*.
16. Su et al., 2026, *Seg2Change*.
17. Guo et al., 2026, *OpenDPR*.
