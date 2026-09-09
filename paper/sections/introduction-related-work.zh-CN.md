# 面向遥感变化描述的证据关联评价：引言与相关工作初稿

> 写作状态：中文论证稿，用于后续改写为 ACM MM 英文正文。  
> 暂定题目：**Beyond Text Similarity: Evidence-Grounded Evaluation for Remote Sensing Change Descriptions**  
> 方法简称：**MGA（Mask-Guided Alignment）**  
> 结果占位说明：本稿只写当前证据能够支撑的论点，不提前填写尚未完成的 SECOND 正式实验数字。

## 论证提纲

1. 遥感变化描述和变化问答正在从封闭模板走向开放语言输出，评价目标应是“描述是否被双时相图像支持”，而不只是“是否复述参考句”。
2. BLEU、METEOR、ROUGE、CIDEr 和 SPICE 等参考文本指标难以区分同义改写与事实错误，也无法指出实体、时相方向或位置中的具体错误。
3. 通用图像描述评价、LLM-as-a-Judge 和事实匹配指标缓解了表面文本偏差，但通常面向单幅自然图像，或仍依赖参考文本/语言模型推理，缺少双时相像素证据。
4. 遥感开放词汇分割与开放词汇变化检测为视觉核验提供了新工具，但分割器误差、数据集封闭类别以及未标注真实物体使“全用 GT”或“全用开放分割”都不充分。
5. MGA 将描述拆解为原子变化声明，并分别核验实体类别、变化方向、空间位置、覆盖度和不可验证性；已知类别使用语义标签，未知类别使用开放词汇掩膜。
6. 论文通过事实图驱动的三类受控样本、四种证据构造、Parser 消融、分割诊断和人工评价验证指标，而不把单一 Overall 分数作为唯一结论。

## 1 引言

双时相遥感影像记录了建筑扩张、道路建设、植被演替和水体变化等地表过程。相比只输出二值变化区域或封闭类别，遥感变化描述（remote sensing change captioning）和变化问答能够用自然语言表达“什么发生了变化、如何变化以及变化位于何处”，因而更接近真实的地理分析需求。近年来，Chg2Cap、Semantic-CC、Change-Agent、Change3D 和 SECOND-CC 等工作不断增强模型的视觉编码、变化建模和语言生成能力，输出也从短模板逐步走向开放、细粒度的描述。然而，生成能力的提升使评价问题变得更加突出：当两个句子使用不同措辞表达同一变化时，低文本相似度不应被视为事实错误；反之，一个流畅且接近参考句式的描述，也可能虚构实体、颠倒新增与移除方向，或把变化定位到错误区域。

现有遥感变化描述研究仍主要报告 BLEU、METEOR、ROUGE-L、CIDEr 和 SPICE 等参考文本指标。例如，SECOND-CC 在提供双时相影像、语义图和五条人工描述的同时，仍以常规 caption 指标作为主要评价协议。此类指标对基准复现十分重要，却把评价目标隐式定义为“与有限参考文本相似”。同一地表事实可以有多种合法表达，而参考描述也不可能穷举图像中的全部变化；因此，文本相似度会同时受到措辞、句法、描述粒度和标注风格的影响。更关键的是，这些分数不能回答一个直接的诊断问题：低分究竟来自语言表达差异，还是来自错误的实体、时相方向或空间关系？

通用图像描述领域已经提出多种超越 n-gram 匹配的指标。TIGEr 和 InfoMetIC 引入图文对齐或细粒度词语—区域反馈，ALOHa 利用开放词汇实体抽取与检测结果识别物体幻觉，CLAIR 等方法使用大语言模型评价语义质量。遥感领域的 FMScore 将变化段落与事实集合进行匹配，ReconScore 则尝试以文本重建视觉内容，降低人工参考风格带来的偏差。这些研究共同说明，评价应从“复述参考句”转向“保留图像事实”。但遥感变化描述具有三个额外约束。第一，证据来自两个时相，而不是单幅图像；实体存在并不等价于其发生了新增、移除或替换。第二，变化声明通常包含实体、方向和位置的组合关系，逐词或逐物体存在性不足以验证完整事实。第三，遥感语义标签常只覆盖少量类别；把标签外真实物体一律判为幻觉，会系统性惩罚更丰富但正确的描述。

开放词汇遥感分割和变化检测为上述问题提供了新的视觉基础。SegEarth-OV 系列使任意文本类别能够在遥感图像中产生像素掩膜；Seg2Change、AdaptOVCD 和 OpenDPR 进一步研究了开放词汇变化定位。然而，开放分割的类别表现并不均衡，且双时相独立分割会把配准误差、尺度差异和稳定存在区域误解释为变化。因此，将开放词汇模型直接作为评价真值同样不可靠。另一方面，语义变化数据集的双时相标签能够精确给出封闭类别的转移事实，却无法核验标签体系之外的树木、河流或其他地物。评价方法需要明确区分“没有证据”“证据反驳”和“类别未被标注”，并在可靠的封闭标签与可扩展的开放视觉证据之间进行路由。

为此，本文提出 Mask-Guided Alignment（MGA），一种面向遥感变化描述与开放式变化回答的证据关联评价框架。给定候选文本、双时相图像及可选的变化/语义标签，MGA 首先把文本规范化为原子声明：

`(entity, change_type, location, role, attributes)`。

随后，评价器为每条声明构造双时相实体掩膜，区分新增、移除和修改证据，并输出空间支持、时相方向、语义覆盖和不可验证率等分量。对于数据集已标注类别，MGA 可以直接使用双时相语义标签；对于未标注类别，则调用开放词汇分割。该设计并不假设开放分割器永远优于标签查找，而是把二者的覆盖范围和误差来源显式暴露出来。MGA 也不以语言流畅度或句式模板为评价目标：只要同义改写在解析后得到相同的原子声明，就应获得一致的视觉事实分数。

为了验证评价器而不是训练新的描述模型，本文从双时相语义标签构建像素级事实图，并为每个场景构造三类受控文本：事实描述、仅替换目标实体的最小矛盾描述，以及保持事实不变的语义改写。该协议同时检验错误敏感性与改写鲁棒性。我们进一步比较四种证据路线：仅做 GT 类别查找的简单基线、仅使用开放词汇分割、已知类用 GT 而未知类用开放分割的 Hybrid，以及使用完整双时相语义转移的 Oracle。Parser 方面，确定性同义词映射负责高精度匹配，轻量级零样本实体抽取器只在词典未命中时补充召回。实验报告每条路线的区分能力、覆盖率、分类别分割 IoU、运行成本和失败类型，并通过人工评价考察自动分量与人类事实判断的一致性。

本文的主要贡献拟概括为：

1. 提出一个面向双时相遥感语言输出的原子声明评价框架，将实体类别、变化方向、空间证据、覆盖度和不可验证性分开报告，避免把不同错误压缩为不可解释的单一分数。
2. 提出基于双时相语义标签的事实图和三类受控评价样本构造方法，用最小事实扰动与语义保持改写同时验证指标的敏感性和鲁棒性。
3. 设计封闭标签与开放词汇掩膜的四路线对照，明确 MaskLabelOnly 的能力边界，并用逐实体证据路由处理部分类别标注场景。
4. 系统分析 Parser、开放词汇分割和标签覆盖对最终评价的贡献与错误传播，为遥感变化描述和变化问答提供可解释、可扩展的诊断协议。

## 2 相关工作

### 2.1 遥感变化描述与变化问答

遥感变化描述的早期研究主要从双分支视觉编码器中提取差异特征，再用循环网络或 Transformer 生成句子。RSICCformer、Chg2Cap 等方法分别从跨时相注意力和变化特征建模角度提升生成质量。后续工作逐渐把像素级变化检测、基础视觉模型和大语言模型引入同一系统：Semantic-CC 使用双时相 SAM 表征和语义变化引导语言解码；Change-Agent 将变化检测、变化描述和进一步问答整合为交互式变化解释代理，并发布含变化掩膜和描述的 LEVIR-MCI；Change3D 则从视频建模角度统一变化检测与描述。与开放描述互补，CDVQA 直接以问题—答案形式查询双时相遥感变化，体现了从固定 caption 向任务驱动语言解释的扩展趋势。

SECOND-CC 对本文尤其重要。它在 SECOND 语义变化数据基础上加入五条人工描述，并保留双时相语义图，从而同时提供语言参考与像素级类别转移。其多类别结构比只标注建筑和道路的变化掩膜更适合检验“简单类别查找是否因标签空间过窄而被高估”。但是，现有 SECOND-CC 工作的主要目标是生成模型，评价仍集中在 BLEU、CIDEr、METEOR、ROUGE-L 和 SPICE；如何把语义图中的时相转移转化为可解释的语言事实核验，仍缺少系统研究。

### 2.2 图像描述的语义与事实评价

传统 caption 指标根据候选文本与参考文本的词汇或语义结构相似度打分，易受参考数量和表达风格影响。TIGEr 较早将图文 grounding 用于 caption 评价；InfoMetIC 同时输出文本精确性、视觉召回和细粒度错误位置；ALOHa 将 LLM 实体抽取、参考对象和检测对象结合，用于开放词汇物体幻觉检测。CLAIR 等 LLM-based metric 能够更灵活地比较语义，但其判断仍可能受提示词、模型版本和语言先验影响。近期综述已将图像描述指标归纳为七十余种，也反映出不存在对所有任务都充分的单一评价分数。

遥感领域开始直接质疑参考指标偏差。FMScore 把生成段落与预定义变化事实逐项匹配，强调事实覆盖而非表面文本；ReconScore 以文本能否支持视觉重建作为参考无关标准。这些思路与 MGA 的目标一致，但 MGA 更关注可定位的双时相证据：不仅判断文本是否提到某一事实，还要求相应实体在正确时相和位置形成可追踪的掩膜证据。换言之，FMScore 更接近“文本—事实集合”匹配，而 MGA 试图实现“原子声明—双时相像素证据”匹配。

### 2.3 开放词汇遥感分割与变化检测

开放词汇语义分割允许模型根据文本查询输出任意类别掩膜，为核验标签体系之外的地物提供了可能。SegEarth-OV-3 面向遥感图像提供原生开放词汇像素分割能力，能够直接以 building、road、tree 或 water 等词语查询双时相影像。与此同时，Seg2Change 通过类别无关变化头将开放词汇分割适配到变化检测；AdaptOVCD 从辐射校准、变化阈值与置信过滤角度组合多个基础模型；OpenDPR 把开放词汇变化检测拆分为类别无关提议和类别识别，并指出细粒度地物类别识别仍是主要瓶颈。

这些研究优化的是变化定位本身，而本文研究的是如何把定位结果用于语言评价。两者的关键差异在于错误责任：开放词汇模型没有分出目标时，不能自动推出文本错误；完整标签中不存在某类，也不能自动推出图像中不存在该物体。因此 MGA 显式报告不可验证状态和 grounder diagnostics，并用 MaskLabelOnly、Open-Vocabulary、Hybrid 和 Oracle 四种路线量化视觉后端对评价结论的实际增益。

### 2.4 本文定位

本文不提出新的变化描述生成器，也不把开放词汇分割性能作为唯一贡献。其核心问题是：在参考文本不完备、语义标签类别受限、开放分割存在噪声的条件下，如何判断一个开放式变化描述是否获得双时相图像证据支持。与纯文本指标相比，MGA 引入可视化的像素证据；与通用单图 grounding 指标相比，MGA 显式建模时相方向和类别转移；与开放词汇变化检测相比，MGA 进一步研究解析误差、证据缺失和人类事实判断之间的关系。

## 3 主张—证据映射

| 论文主张 | 所需证据 | 当前状态 |
|---|---|---|
| 文本相似度不能充分反映遥感变化事实 | 文献分析；事实改写与最小矛盾样本上的排序对比 | 受控样本构造已实现，待正式批量结果 |
| MaskLabelOnly 在封闭类别内是强基线，但无法处理标签外实体和时相关系 | GT 类别查找、隐藏类条件和 Oracle 对照 | 四路线实现与冒烟已完成 |
| 轻量 NER 应作为词典未命中补充，而不是替代规则 Parser | 标准模板集与表面表达压力集的 precision/recall、耗时 | 冒烟结果支持，待完整集复核 |
| 纯开放词汇分割受类别性能限制 | 分类别 pre/post/add/remove IoU 与可视化 | 冒烟已观察到类别差异，待约 200 场景 |
| Hybrid 在部分类别标注条件下比单一路线更合理 | closed-set 与 hidden-class 两种条件的 AUC、balanced accuracy、coverage | 冒烟已跑通，待正式置信区间 |
| MGA 的分量与人类事实判断相关 | 多评审人工评价、配对统计与置信区间 | 已有 50 场景三评审 pilot，仍需独立 held-out |

## 4 参考文献入口

- Karaca et al. 2025, [Robust Change Captioning in Remote Sensing: SECOND-CC Dataset and MModalCC Framework](https://doi.org/10.1109/JSTARS.2025.3600613)
- Chang and Ghamisi 2023, [Changes to Captions: An Attentive Network for Remote Sensing Change Captioning](https://arxiv.org/abs/2304.01091)
- Liu et al. 2024, [Change-Agent: Towards Interactive Comprehensive Remote Sensing Change Interpretation and Analysis](https://arxiv.org/abs/2403.19646)
- Liu et al. 2021, [CDVQA: A Benchmark Dataset for Change Detection Visual Question Answering](https://arxiv.org/abs/2112.06343)
- Zhu et al. 2025, [Change3D: Revisiting Change Detection and Captioning from a Video Modeling Perspective](https://openaccess.thecvf.com/content/CVPR2025/html/Zhu_Change3D_Revisiting_Change_Detection_and_Captioning_from_A_Video_Modeling_CVPR_2025_paper.html)
- Liu et al. 2024, [Semantic-CC: Boosting Remote Sensing Image Change Captioning via Foundational Knowledge and Semantic Guidance](https://arxiv.org/abs/2407.14032)
- Hu et al. 2023, [InfoMetIC: An Informative Metric for Reference-free Image Caption Evaluation](https://aclanthology.org/2023.acl-long.178/)
- Petryk et al. 2024, [ALOHa: A New Measure for Hallucination in Captioning Models](https://aclanthology.org/2024.naacl-short.30/)
- Jiang et al. 2019, [TIGEr: Text-to-Image Grounding for Image Caption Evaluation](https://aclanthology.org/D19-1220/)
- Lee et al. 2025, [Surveying the Landscape of Image Captioning Evaluation](https://aclanthology.org/2025.tacl-1.73/)
- Chen et al. 2026, [Evaluating Remote Sensing Image Captions Beyond Metric Biases](https://arxiv.org/abs/2604.22855)
- [Remote Sensing Change Captioning Meets Large Language and Vision Models / FMScore](https://www.sciencedirect.com/science/article/pii/S0924271626003035)
- Su et al. 2026, [Seg2Change: Adapting Open-Vocabulary Semantic Segmentation Model for Remote Sensing Change Detection](https://arxiv.org/abs/2604.11231)
- Guo et al. 2026, [OpenDPR: Open-Vocabulary Change Detection via Vision-Centric Diffusion-Guided Prototype Retrieval](https://openaccess.thecvf.com/content/CVPR2026/html/Guo_OpenDPR_Open-Vocabulary_Change_Detection_via_Vision-Centric_Diffusion-Guided_Prototype_Retrieval_for_CVPR_2026_paper.html)
- [SegEarth-OV-3 implementation](https://github.com/earth-insights/SegEarth-OV-3)

## 5 自检记录

- 引言是否只陈述已被当前文献或实验设计支持的论点：是；未写正式 SECOND 数字。
- 是否把研究缺口具体化：是；缺口被限定为双时相、原子声明级、可定位证据评价。
- 是否夸大新颖性：否；明确承认 TIGEr、InfoMetIC、ALOHa、FMScore 和开放词汇变化检测的基础。
- 是否把 MGA 错写成新的分割模型：否；明确定位为评价与诊断框架。
- 是否把单一 Overall 当作最终结论：否；强调分量、覆盖率和不可验证率。
- 正式英文稿仍需补充：统一 BibTeX、最终实验数字、bootstrap 95% CI、显著性检验、失败案例图和人工评价协议。
