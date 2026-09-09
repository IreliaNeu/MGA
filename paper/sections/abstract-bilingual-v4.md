# MGA Abstract v4 / 摘要 v4

> 主线：从参考文本相似度转向双时相 Claim—Evidence 验证  
> 主方法：MGA-Hybrid  
> 写作策略：弱化数据集规模罗列，突出核心逻辑、关键结果与适用边界  
> 结构：七句式（Task → Problem → Insight → Challenge → Method → Evidence → Result）

## 中文摘要

开放式遥感变化描述旨在用自然语言解释双时相影像中的地表变化，而可靠评价是比较生成模型与识别事实错误的基础。现有 BLEU、CIDEr、METEOR 和 ROUGE-L 等参考文本指标主要衡量候选输出与有限参考表达的相似程度，难以直接识别事实保持改写以及实体、时相方向和空间关系错误。本文的核心思想是将评价问题从“候选文本是否像参考答案”转化为“文本中的原子变化声明能否在双时相图像中获得一致证据”。这一目标要求评价器既利用已有语义标注的可靠空间信息，又能处理标签外实体和开放词汇视觉定位的不确定性，并区分事实反驳与证据不足。为此，我们提出 Mask-Guided Alignment（MGA），通过领域 Claim 解析、逐实体 Hybrid 证据路由和 Add、Remove、Modify 及 source-to-target 关系构造，输出 Spatial、Temporal、Fact Coverage 和 Verifiability 等可解释诊断。我们在真实模型输出、人工判断、受控事实扰动和不同标注可用性条件下检验 MGA 的事实敏感性、表达鲁棒性与证据边界。结果表明，随着可用语义类别由 0% 逐步增加至 100%，MGA-Hybrid 的 Neutral AUC 从 0.522 提升至 0.944、Balanced Accuracy 从 0.553 提升至 0.935，同时可评分覆盖率提升至 1.000、不可验证率降至 0；对经显式 Claim 等价约束确认的事实保持改写，MGA 保持一致诊断，而传统文本指标下降约 18%–21%，验证了双时相证据评价相对于单纯参考匹配的互补价值。

## English Abstract

Open-ended remote-sensing change captioning explains land-surface changes in bi-temporal imagery with natural language, making reliable evaluation essential for comparing generators and identifying factual errors. Existing reference-based metrics such as BLEU, CIDEr, METEOR, and ROUGE-L mainly measure similarity to a limited set of reference expressions and cannot directly distinguish claim-preserving rewrites from errors in entities, temporal directions, or spatial relations. Our central insight is to reformulate evaluation from asking whether a candidate resembles a reference to asking whether its atomic change claims are supported by consistent evidence in the image pair. This objective requires an evaluator to exploit reliable spatial information from available semantic annotations while handling entities outside the label space, noisy open-vocabulary localization, and the distinction between contradiction and insufficient evidence. We therefore introduce Mask-Guided Alignment (MGA), which combines domain-aware claim parsing, entity-wise Hybrid evidence routing, and Add, Remove, Modify, and source-to-target relation construction to produce interpretable Spatial, Temporal, Fact Coverage, and Verifiability diagnostics. We assess MGA using real model outputs, human judgments, controlled factual perturbations, and progressively varying annotation availability, thereby testing factual sensitivity, linguistic robustness, and evidence boundaries. As semantic-class availability increases from 0% to 100%, MGA-Hybrid improves Neutral AUC from 0.522 to 0.944 and Balanced Accuracy from 0.553 to 0.935 while reaching full evaluation coverage and reducing the Unverifiable Rate to zero; on claim-preserving rewrites validated under an explicit claim-equivalence constraint, MGA retains identical diagnoses while conventional text metrics decrease by approximately 18%–21%, demonstrating the complementary value of bi-temporal evidence verification beyond reference matching.

## 反向提纲

1. 任务：遥感变化描述需要可靠评价。
2. 问题：参考文本指标不能直接验证双时相事实。
3. 洞见：评价原子 Claim 是否得到图像证据。
4. 挑战：有限语义标签、开放视觉噪声与证据不足。
5. 方法：Claim 解析、Hybrid 路由和关系证据。
6. 证据：真实输出、人工判断、受控扰动和标注可用性。
7. 结果：Hybrid 的判别力与可评分覆盖提高，事实保持改写下 MGA 更稳定。

## Claim—Evidence 对照

- Claim：参考相似度不能充分代表图像事实性。  
  Evidence：事实保持强改写使 BLEU/ROUGE/Token-F1 下降约 18%–21%，而 MGA 诊断不变。  
  Status：supported under claim-equivalent rewrites。

- Claim：Hybrid 在不同标注可用性条件下形成准确性—覆盖折中。  
  Evidence：完整 64 个类别子集的标注可用性曲线，Neutral AUC、Balanced Accuracy、Evaluation Coverage 和 Unverifiable Rate 共同报告。  
  Status：supported in the controlled SECOND-CC setting。

- Claim：MGA 与真实人工判断一致。  
  Evidence：现有 50 场景三评审 pilot 支持 Temporal 分量，但独立人工测试集尚未完成。  
  Status：needs final evidence；摘要目前只写“检验”，不宣称已经全面优于其他指标。

- Claim：MGA 完全无标注部署。  
  Evidence：No-ROI、RGB 特征差分和预测 CD ROI 已完成，但测试集 Neutral AUC 分别为 0.748、0.720 和 0.689；预测 ROI 未优于 No-ROI，纯 OV 标注可用性端点也接近随机。  
  Status：unsupported；只能表述为支持无测试 GT 的扩展，并明确开放证据仍是瓶颈。

## 摘要自审

- [x] 主线从任务失败、方法洞见到结果保持单一因果链。
- [x] 删除 200 场景、600 文本和 64 子集等密集规模罗列。
- [x] 保留最能支撑方法逻辑的关键数字。
- [x] 区分 Fact Coverage 与 evaluation coverage。
- [x] 不宣称真实开放 QA 已经验证成功。
- [x] 不宣称 MGA-OV 已实现完全无标注部署。
- [ ] 完成独立人工效度和强基线后，再将“using real model outputs and human judgments”改为更强的比较结论。
