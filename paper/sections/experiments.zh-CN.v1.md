# 4 实验

> 已合并至 [实验章节 v2](experiments.zh-CN.v2.md)，本文件保留为历史稿。

> 文档状态：中文实验章节 v1。  
> 写作约定：`[已完成]` 表示已有归档结果；`[待补实验]` 表示为投稿实验预留的位置，不能在摘要或正文中当作既成结论。  
> 主线：参考匹配失效 → 双时相 Claim—Evidence 验证 → Hybrid 准确性—覆盖折中 → 人工效度与错误类型验证。
>
> **2026-09-06 版本提示：** 本文件是实验章节的基础稿，部分表格仍保留历史 `TBD`。统一五模型输出、ALOHa-local、FMScore-Qwen、Grounding DINO Tiny/Base、七类最小错误、Predicted-ROI、Selective Prediction 及传统指标结果已经完成，分别见 `experiments-p0-update-2026-08-12.zh-CN.md`、`experiments-factual-baselines-update-2026-08-13.zh-CN.md` 和 `docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md`。当前真正影响投稿闭环的主要缺口是独立、盲化、held-out 的多人 Claim 级人工效度实验，以及将这些结果合并进最终英文 LaTeX；不要把本稿中的历史占位符当作项目当前状态。

## 4.1 实验目标与研究问题

本节围绕 MGA 是否真正衡量双时相图像事实，而不是复现参考文本或查询标签类别，回答以下四个研究问题。

1. **RQ1：事实敏感性。** MGA 能否区分事实正确描述、事实保持改写和仅包含一个关键事实错误的描述？
2. **RQ2：Hybrid 必要性。** 在语义标注不完整时，逐实体组合封闭语义证据与开放视觉证据，能否优于纯 GT 查找或纯开放词汇定位？
3. **RQ3：分量效度。** Spatial、Temporal、Fact Coverage 和 Verifiability 是否分别对应人类可识别的实体、方向、遗漏与证据不足问题？
4. **RQ4：现实边界。** 当 Parser、开放分割或变化 ROI 不可靠时，MGA 的性能如何退化，哪些结论仍然成立？

这四个问题形成同一证据链：RQ1验证评价目标，RQ2验证主方法，RQ3说明可解释分量的必要性，RQ4限定方法的实际适用范围。变化问答和LLM Parser只检验接口或工程扩展，不作为平行研究主线。

## 4.2 实验设置

### 4.2.1 数据集与任务分工

**LEVIR-MCI。** LEVIR-MCI提供配准的双时相影像、变化描述以及道路和建筑变化掩膜。本研究使用该数据集评价真实生成模型输出，并开展人工事实性评审、道路/建筑分层以及变化方向分析。现有归档包含Change-Agent、Draft、Refined、RSICCformer和Chg2Cap五类描述来源；其中后两者来自独立官方模型家族。

**SECOND-CC。** SECOND-CC提供双时相语义标签和多类别变化描述，适合从像素级转移构建事实图。本研究从其中选择200个场景，为每个场景构造factual、claim-preserving paraphrase和target-entity contradiction三类文本，共600条受控样本。该数据集承担多类别证据路由、标注可用性和开放词汇瓶颈分析，不替代真实模型输出上的人工效度实验。

两个数据集具有互补作用：LEVIR-MCI提供真实输出和清晰的道路/建筑人工判断，SECOND-CC提供多类别、双时相语义事实与可控的标签隐藏条件。论文不要求每个数据集同时承担所有验证任务。

### 4.2.2 候选文本

当前候选文本包括：

- LEVIR-MCI真实输出：Change-Agent、Draft和Refined；
- SECOND-CC受控事实描述；
- 保持实体与变化关系不变的释义；
- 仅替换一个目标实体的最小矛盾描述；
- 强风格改写；
- 小规模受控变化问答回答。

`[已完成：RSICCformer与Chg2Cap各1000条对齐输出；固定100场景MGA pilot]`

正式投稿将增加两个独立变化描述模型家族。所有输出使用统一清单：

| 模型家族 | 模型版本/权重 | 输出数量 | 生成配置 | 状态 |
|---|---|---:|---|---|
| Change-Agent | 待固化 | 待填 | 已有输出，待补provenance | 部分完成 |
| RSICCformer | 官方checkpoint | 1000 | greedy/官方设置 | 完成；清单审计通过 |
| Chg2Cap | 官方checkpoint | 1000 | greedy/官方设置 | 完成；清单审计通过 |
| Human reference | 数据集提供 | `TBD` | 不适用 | 待汇总 |
| Optional zero-shot VLM | `TBD` | `TBD` | 固定prompt | 可选 |

Change-Agent的Draft与Refined属于同一生成家族的不同处理阶段，统计时不会将其视为两个完全独立模型。

RSICCformer和Chg2Cap已完成官方仓库固定、LEVIR-MCI 1,929对test索引、与MGA清单重合的1,000对索引以及官方词表构建。两份官方权重均通过SHA-256与容器CRC校验；两模型各生成1000条描述，缺失、重复、空文本和清单外样本均为0。RSICCformer仅增加新版PyTorch causal-hint参数兼容处理，不改变模型数值运算；Chg2Cap补充其官方依赖`einops==0.4.1`。

### 4.2.3 比较方法

**传统参考指标。** 正式版本统一计算BLEU-1/4、METEOR、ROUGE-L、CIDEr、SPICE和BERTScore。这些指标衡量语言或参考一致性，不被解释为图像事实性真值。

**图文或事实指标。** `[待补实验]` 至少加入一个图文相似度基线和一个事实评价基线，候选包括CLIPScore/RemoteCLIPScore以及能够稳定复现的FMScore、ALOHa或InfoMetIC。

**MGA证据路线。**

1. `GTClassLookup/MaskLabelOnly`：直接检查Parser映射类别在变化标签中的存在与覆盖，是最强简单基线；
2. `MGA-OV`：使用开放词汇双时相实体掩膜构造关系证据；
3. `MGA-Hybrid`：已标注类别使用GT证据，标签外实体使用开放词汇证据；
4. `OracleAllClass`：所有类别均使用完整双时相语义转移，表示证据上界。

当前MGA-OV的受控实验使用真实变化ROI，因此正文中应标记为`MGA-OV + Oracle GT-ROI`，不能将其解释为完全无标注部署。

### 4.2.4 评价指标

设共有 \(N\) 个待评样本，其中 \(N_s\) 个获得数值分数，则可评分覆盖率为

\[
\mathrm{EvalCoverage}=\frac{N_s}{N}.
\]

该指标与方法内部的Fact Coverage不同：Fact Coverage衡量文本证据覆盖真实变化连通分量的程度，而Evaluation Coverage衡量评价器能否为样本给出数值判断。

对不可验证样本赋中性分数0.5后计算Neutral AUC：

\[
\mathrm{NeutralAUC}
=
\operatorname{AUC}
\left(
\{(y_i,\tilde s_i)\}_{i=1}^{N}
\right),\qquad
\tilde s_i=
\begin{cases}
s_i,&s_i\ \text{available},\\
0.5,&s_i\ \text{unverifiable}.
\end{cases}
\]

Balanced Accuracy仅在获得数值分数的样本上、以0.5为支持阈值计算。False Support Rate定义为矛盾样本中得分不低于0.5的比例：

\[
\mathrm{FSR}
=
\frac{
\sum_i \mathbb{1}[y_i=0\land s_i\ge 0.5]
}{
\sum_i \mathbb{1}[y_i=0]
}.
\]

不可验证率为

\[
\mathrm{U}=1-\mathrm{EvalCoverage}.
\]

人工实验进一步报告Fleiss \(\kappa\) 或Krippendorff's \(\alpha\)、Spearman/Kendall相关、pairwise accuracy和场景级bootstrap置信区间。MGA的Spatial、Temporal和Fact Coverage分别与人工实体/位置、变化方向和事实完整性判断对齐，不用一个未经校准的Overall替代全部维度。

### 4.2.5 实现与统计

SegEarth-OV-3用于开放词汇实体分割，当前置信度门槛为0.10。Claim状态的Contradicted和Supported阈值分别为0.25和0.60；这些阈值在现有实验中固定，但正式投稿应在独立development子集上校准。SECOND-CC结果使用场景级bootstrap，共2,000次重采样，随机种子为20260726。

`[待补实验：计算成本]`

| 模块 | 单场景时延 | 峰值显存 | 缓存体积 | 硬件 |
|---|---:|---:|---:|---|
| Parser Rule-only | `TBD` | `TBD` | `TBD` | `TBD` |
| Parser Rule+LLM | `TBD` | `TBD` | `TBD` | `TBD` |
| SegEarth evidence | `TBD` | `TBD` | `TBD` | RTX 4090 |
| Predicted ROI | `TBD` | `TBD` | `TBD` | `TBD` |
| MGA scoring | `TBD` | `TBD` | `TBD` | CPU |

## 4.3 主要结果：标注可用性下的MGA-Hybrid

### 4.3.1 实验设计

`[已完成]`

为模拟现实中类别标注逐步增加的条件，我们枚举SECOND-CC六个语义类别的完整幂集。对每个类别子集，可用类别直接使用GT语义证据，不可用类别回退到SegEarth双时相掩膜。对同一标注比例，结果在所有同规模类别子集上取均值，并保留最小值—最大值，以区分“标注比例”和“标注了哪些类别”两种因素。

### 4.3.2 标注可用性曲线

| 可用类别 | 子集数 | Eval. Coverage ↑ | Neutral AUC ↑ | Balanced Acc. ↑ | FSR ↓ | U ↓ |
|---:|---:|---:|---:|---:|---:|---:|
| 0/6 | 1 | 0.915 | 0.522 | 0.553 | 0.156 | 0.085 |
| 1/6 | 6 | 0.929 | 0.590 | 0.595 | 0.181 | 0.071 |
| 2/6 | 15 | 0.943 | 0.658 | 0.647 | 0.188 | 0.057 |
| 3/6 | 20 | 0.957 | 0.727 | 0.707 | 0.179 | 0.043 |
| 4/6 | 15 | 0.971 | 0.797 | 0.776 | 0.155 | 0.029 |
| 5/6 | 6 | 0.986 | 0.869 | 0.852 | 0.119 | 0.014 |
| 6/6 | 1 | 1.000 | 0.944 | 0.935 | 0.070 | 0.000 |

Neutral AUC和Balanced Accuracy随可用语义类别增加而稳定提高，说明可靠语义证据能够逐步转化为更强的事实判别能力。与此同时，Evaluation Coverage从0.915提高到1.000，Unverifiable Rate从0.085下降到0，说明Hybrid在开放证据不充分时允许弃权，并在可靠证据增加后恢复可评分性。

FSR在低标注阶段先升后降，而不是严格单调。当只有一部分source或target实体获得精确GT证据时，另一端的开放掩膜噪声可能与准确端形成偶然关系，导致错误支持率暂时增加。该现象限定了论文结论：Hybrid提供总体准确性—覆盖折中，但少量任意类别标注不保证所有风险指标立即改善。

同为50%标注可用性时，不同类别组合的Neutral AUC范围为0.656–0.833，Balanced Accuracy为0.608–0.824，FSR为0.109–0.241，Evaluation Coverage为0.920–0.995。这表明类别组成与标注比例同样重要，后续类别边际贡献实验应解释哪些类别最值得优先标注。

主图： [Label availability curve](../figures/fig_label_availability_curve.pdf)

### 4.3.3 OV门槛敏感性

| OV门槛 | 0% Coverage | 0% U | 0% Neutral AUC | 50% Coverage | 50% Neutral AUC | 100% AUC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.915 | 0.085 | 0.522 | 0.957 | 0.727 | 0.944 |
| 0.10 | 0.915 | 0.085 | 0.522 | 0.957 | 0.727 | 0.944 |
| 0.20 | 0.853 | 0.147 | 0.504 | 0.925 | 0.728 | 0.944 |

0.05与0.10得到相同结果，说明当前低阈值区间内，掩膜存在性约束比置信度门槛更具决定性。0.20主要增加了低标注阶段的弃权，并未改善50%标注处的AUC。正式实验仍需在独立development子集固定门槛，避免根据测试曲线选择参数。

## 4.4 四路证据对照

### 4.4.1 完整类别条件

`[已完成]`

| 方法 | Eval. Coverage ↑ | AUC ↑ | Balanced Acc. ↑ | FSR ↓ |
|---|---:|---:|---:|---:|
| GTClassLookup | 1.000 | 0.875 | 0.875 | 0.250 |
| OpenVocabOnly | 1.000 | 0.580 | 0.560 | 0.130 |
| MGA-Hybrid | 1.000 | **0.944** | **0.935** | **0.070** |
| OracleAllClass | 1.000 | 0.958 | 0.958 | 0.075 |

GTClassLookup只检查source和target原子事件是否存在，无法要求二者在同一局部变化区域形成关系，因此产生较高FSR。纯开放词汇证据保持覆盖，但受分割噪声限制，判别力较弱。Hybrid进一步验证source-remove和target-add的局部关系，在受控条件下接近完整语义Oracle。相对OpenVocabOnly，Hybrid的AUC提高0.364，场景级95%置信区间为[0.318, 0.413]。

### 4.4.2 隐藏类别条件

`[已完成]`

| 方法 | Eval. Coverage ↑ | Neutral AUC ↑ | Balanced Acc. ↑ | FSR ↓ |
|---|---:|---:|---:|---:|
| GTClassLookup | 0.195 | 0.636 | 0.886* | 0.229 |
| OpenVocabOnly | 1.000 | 0.580 | 0.560 | 0.130 |
| MGA-Hybrid | **1.000** | **0.711** | **0.702** | 0.180 |
| OracleAllClass | 1.000 | 0.958 | 0.958 | 0.075 |

\* GTClassLookup的Balanced Accuracy仅在19.5%已评分样本上计算，不能与全覆盖方法直接比较。

隐藏tree、low vegetation和water后，GTClassLookup出现明显coverage collapse；Hybrid通过开放词汇回退保持完整可评分覆盖，并相对OpenVocabOnly获得0.131 AUC增益，其95%置信区间为[0.094, 0.168]。该结果支持逐实体路由，但同时表明隐藏类别的开放视觉证据仍远低于Oracle，是当前主要性能瓶颈。

## 4.5 人工效度先导实验

### 4.5.1 评审一致性

`[已完成：pilot，不作为最终独立人工结论]`

现有人工先导包含50个LEVIR-MCI场景、每场景3条候选描述和3名评审。整体正确性题具有中等一致性，而“GT是否漏标”和主观偏好的一致性较低。

| 人工题目 | 完全一致率 | Fleiss \(\kappa\) |
|---|---:|---:|
| Change-Agent描述正确 | 0.620 | 0.418 |
| Draft描述正确 | 0.700 | 0.524 |
| Refined描述正确 | 0.740 | 0.606 |
| Refined新增细节正确 | 0.460 | 0.272 |
| 正确实体未被GT覆盖 | 0.122 | -0.171 |
| 三描述偏好 | 0.460 | 0.315 |

负的GT漏标一致性说明原问题混合了“图中存在实体”“实体发生变化”和“GT覆盖变化区域”三个概念。正式人工协议必须拆分这些维度，不能沿用该题作为主结论。

### 4.5.2 MGA分量与人工判断

| 模式/分量 | 有效样本 | ROC-AUC ↑ | Balanced Acc. ↑ |
|---|---:|---:|---:|
| Full / Overall | 149 | 0.466 | 0.584 |
| MaskLabelOnly / Overall | 149 | **0.593** | **0.644** |
| Hybrid / Overall | 149 | 0.512 | 0.639 |
| Full / Faithfulness | 142 | 0.448 | 0.457 |
| MaskLabelOnly / Faithfulness | 142 | **0.625** | 0.612 |
| Hybrid / Faithfulness | 142 | 0.519 | 0.612 |
| Full或Hybrid / Temporal | 93 | **0.782** | **0.739** |
| MaskLabelOnly或Hybrid / Coverage | 149 | 0.610 | 0.619 |

人工pilot揭示了方法设计中一个重要边界：MaskLabelOnly是标签范围内很强的空间基线，当前未经校准的Hybrid Overall并未优于它；SegEarth最明确的增益来自Temporal分量。由此，主方法应解释为“可靠GT空间/覆盖证据 + 开放双时相方向证据”的分量式Hybrid，而不是将所有分量强行压缩为单一总分。

`[待补实验：最终人工效度]`

| 设置 | 场景数 | Caption数 | 评审数 | 盲化 | 状态 |
|---|---:|---:|---:|---|---|
| Pilot | 50 | 150 | 3 | 否 | 已完成 |
| Development | `TBD` | `TBD` | 3 | 是 | 待补 |
| Independent test | `TBD` | `TBD` | 3 | 是 | 待补 |

正式测试将按Claim标注实体、方向、位置、关系和证据充分性，并将事实性、完整性和流畅性分开评价。阈值仅在development上选择，test用于最终相关性与显著性分析。

## 4.6 对事实保持改写的鲁棒性

`[已完成：补充机制实验]`

强风格压力实验对20条原始描述分别生成technical nominalized和active narrative两种改写，共40条。30条改写通过显式Claim签名等价门控；其余10条发生semantic drift，不计入不变性结论。

| 指标 | 原始描述对参考 | 风格改写对同一参考 | 相对变化 |
|---|---:|---:|---:|
| BLEU-1 | 0.327 | 0.273 | -16.8% |
| BLEU-4 | 0.188 | 0.150 | -20.4% |
| ROUGE-L | 0.325 | 0.256 | -21.3% |
| Token F1 | 0.328 | 0.267 | -18.6% |
| MGA status agreement | 1.000 | 1.000 | 0 |
| MGA mean absolute delta | 0 | 0 | 0 |

这些结果支持一个有边界的结论：当实体、方向、位置和属性Claim保持不变时，MGA复用同一图像证据并保持诊断，而有限参考文本指标仍受到词汇和句法风格影响。由于当前等价门控仍依赖MGA Parser，正式实验还需人工或独立Parser验证改写等价性，以排除自我验证。

`[待补实验：官方指标与独立等价标注]`

| 指标 | 原始 | 改写 | 差值 | 95% CI | 状态 |
|---|---:|---:|---:|---:|---|
| Corpus BLEU-4 | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| METEOR | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| CIDEr | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| BERTScore | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| MGA-Hybrid | `TBD` | `TBD` | `TBD` | `TBD` | 待补独立门控 |

## 4.7 Parser与视觉证据误差

### 4.7.1 Parser

`[已完成：受控surface-form]`

| Parser | Exact Match ↑ | Precision ↑ | Recall ↑ | F1 ↑ |
|---|---:|---:|---:|---:|
| 基础ontology | 0.500 | 1.000 | 0.500 | 0.667 |
| 基础ontology + GLiNER | 0.518 | 0.947 | 0.650 | 0.770 |
| 配置化ontology | **1.000** | **1.000** | **1.000** | **1.000** |
| 配置化ontology + GLiNER | 0.927 | 0.965 | **1.000** | 0.982 |

受控结果表明，领域配置词表是高精度解析的必要基础，无条件运行轻量实体模型会引入额外假阳性。但该1.000结果只覆盖预设surface-form，不能外推到真实开放语言。

`[待补实验：真实文本LLM fallback]`

| Parser | Entity F1 ↑ | Canonical Acc. ↑ | Direction F1 ↑ | Relation EM ↑ | Abstention | MGA AUC | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| Rule-only | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| LLM-only | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| Rule + LLM fallback | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | 待补 |
| Oracle Claim | 1.000 | 1.000 | 1.000 | 1.000 | 0 | `TBD` | 待补 |

LLM只负责从文本生成受本体约束的结构化Claim，不访问图像、不决定事实是否正确。若LLM fallback不能改善真实输出上的召回—精确率折中，则Rule-only保留为主Parser。

### 4.7.2 SegEarth定位瓶颈

`[已完成]`

| 类别 | Pre IoU | Post IoU | Add IoU | Remove IoU |
|---|---:|---:|---:|---:|
| building | 0.119 | 0.129 | **0.189** | **0.160** |
| low vegetation | 0.084 | 0.104 | 0.078 | 0.070 |
| non-vegetated ground | 0.070 | 0.082 | 0.047 | 0.053 |
| playground | 0.034 | 0.051 | 0.051 | 0.017 |
| tree | 0.050 | 0.048 | 0.048 | 0.059 |
| water | 0.074 | 0.059 | 0.041 | 0.068 |

建筑是当前最稳定类别，而低植被、裸地、树木和操场存在明显过分割或混淆。这解释了纯开放词汇路线接近弱判别水平，也说明Hybrid的价值不是宣称SegEarth已经足够准确，而是在标签不完整时保留开放覆盖，并将已知类别交给更可靠的语义证据。

## 4.8 预测变化ROI与无GT部署

`[已完成：SECOND-CC 200场景阈值校准；LEVIR-MCI 50场景ROI质量复核]`

现有GT-ROI用于隔离实体Grounder误差，只能作为Oracle条件。我们固定实体证据，仅替换变化门控，比较：

1. Oracle GT-ROI；
2. 固定的Predicted-CD probability map；
3. 双时相RGB特征差分ROI；
4. No-ROI。

预测ROI以软门控方式作用于实体时相差分：

\[
\widehat E_{\mathrm{add}}
=
\operatorname{ReLU}(M^2_e-M^1_e)
\odot
\left[\lambda+(1-\lambda)P_{\mathrm{change}}\right],
\]

\[
\widehat E_{\mathrm{remove}}
=
\operatorname{ReLU}(M^1_e-M^2_e)
\odot
\left[\lambda+(1-\lambda)P_{\mathrm{change}}\right].
\]

表中SECOND-CC结果采用97个development场景选择阈值、103个互斥test场景报告结果；AUC为Neutral AUC。ChangeFormer使用LEVIR-CD官方权重，属于跨域预测ROI压力测试。

| ROI模式 | SECOND ROI IoU ↑ | Test AUC ↑ | Test Balanced Acc. ↑ | Test FSR ↓ | Test U ↓ |
|---|---:|---:|---:|---:|---:|
| Oracle GT-ROI | 1.000 | 0.739 | 0.729 | **0.175** | 0.032 |
| Predicted-CD ROI | 0.011 | 0.693 | 0.713 | 0.258 | 0.032 |
| Feature-difference ROI | 0.141 | 0.720 | 0.737 | 0.289 | 0.032 |
| No-ROI | — | **0.748** | **0.746** | 0.309 | 0.032 |

固定0.5阈值时，Predicted-CD的Balanced Accuracy仅为0.505；在development场景上校准到0.10后，独立test提升到0.713。这说明预测变化分数不是概率，必须在独立开发集校准。Predicted-CD没有在AUC或Balanced Accuracy上超过No-ROI，但将FSR从0.309降至0.258，形成更保守的部署折中。由于ChangeFormer在SECOND上的ROI IoU仅0.011，该结果应表述为明显域偏移下的下界，而非最佳预测ROI性能。

在与训练域一致的LEVIR-MCI 50场景上，Change-Agent MCI的预测ROI达到0.509 macro IoU，明显优于RGB差分的0.034；其预测变化比例0.050也接近参考的0.059。这一结果表明Predicted-ROI路线本身可行，但其价值依赖变化检测器的领域匹配。论文因此不宣称MGA在任意域上完全无标注部署，而将MGA-Hybrid作为主方法、Predicted-ROI作为无测试GT的现实扩展，并显式报告Oracle gap。

## 4.9 最小错误类型分解

`[已完成：SECOND-CC 200场景，1600条单因素样本]`

为了验证各分量确实对应不同事实错误，我们从每个正确描述构造七种最小对照，每次只修改一个Claim字段。表中报告MGA-Hybrid的benchmark diagnostic score；该分数为所有已表达事实的证据合取与受控事实图原子覆盖率的乘积。

| 错误类型 | 目标分量 | Pairwise Acc. ↑ | AUC ↑ | FSR ↓ | U ↓ | 状态 |
|---|---|---:|---:|---:|---:|---|
| 错误实体 | Entity support | 0.735 | 0.823 | 0.000 | 0.000 | 完成 |
| Add/Remove颠倒 | Temporal | 0.735 | 0.868 | 0.000 | 0.000 | 完成 |
| 错误位置 | Location | 0.410 | 0.673 | 0.380 | 0.000 | 完成 |
| 错误source-to-target | Relation | 0.735 | 0.868 | 0.000 | 0.000 | 完成 |
| 虚构变化 | Claim support/FSR | 0.385 | 0.688 | 0.355 | 0.000 | 完成 |
| 遗漏变化 | Atomic fact coverage | 0.730 | 0.742 | 0.000 | 0.000 | 完成* |
| No-change误报 | Temporal/FSR | 0.742 | 0.866 | 0.000 | 0.010 | 完成 |
| 数量/属性错误 | Attribute | `TBD` | `TBD` | `TBD` | `TBD` | 可选 |

方向、实体、关系和no-change错误被稳定识别；位置与虚构变化仍是主要薄弱点。MGA-GT在位置错误上的AUC也只有0.744、FSR为0.500，说明该问题不仅来自开放分割噪声，也与粗粒度位置划分和大目标跨区有关。

\* 遗漏错误需要事实图或参考语义才能定义“未表达的事实”。作为必要的负对照，当只使用reference-free evidence score时，三条路线的遗漏Pairwise Accuracy均为0，MGA-Hybrid的AUC降至0.417、FSR升至0.875。因此，正文不能声称纯视觉证据在无事实图条件下能够检测任意遗漏；Fact Coverage应明确为有参考事实图时的诊断分量。

### 4.9.1 选择性预测

我们进一步使用与事实分数独立的视觉掩膜置信度对样本排序。MGA-Hybrid在近全覆盖时准确率为0.873、FSR为0.105；保留最高置信度的19.3%样本时，准确率提升到0.961、FSR下降到0.041；在25.1%覆盖率时分别为0.945和0.058。MGA-Hybrid的AURC为0.095，优于MGA-OV的0.173。该结果支持将“不确定时拒答”作为部署协议，但风险—覆盖曲线并非严格单调，阈值必须在开发集固定，不能按测试结果挑选。

### 4.9.2 独立变化描述模型输出

`[已完成：1000条生成清单；固定100场景、200条描述的MGA pilot]`

为检验MGA是否依赖Change-Agent单一输出分布，我们使用官方RSICCformer和Chg2Cap checkpoint在同一LEVIR-MCI测试索引上生成描述。两模型各有1000条输出通过严格清单审计。RSICCformer产生239种唯一描述，其中465条为精确no-change模板；Chg2Cap产生157种唯一描述，其中502条为精确no-change模板。两模型在488/1000个场景上输出完全相同的句子，说明它们共享LEVIR-CC的模板偏好，但仍保留足够的非重合输出用于多模型适配性检查。

我们进一步使用生成前已固定的100场景building/road子集，复用相同SegEarth-OV-3双时相掩膜，并以当前Parser为两模型共200条描述生成claims。所有场景均通过图像路径、变化掩膜、模型集合和Parser审计。结果如下：

| 证据模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| Full target | RSICCformer | 0.547 | 0.833 | 0.877 | 0.669 | 0.378 |
| Full target | Chg2Cap | 0.563 | 0.837 | 0.892 | 0.683 | 0.357 |
| Temporal delta | RSICCformer | 0.561 | 0.800 | 0.877 | 0.668 | 0.375 |
| Temporal delta | Chg2Cap | 0.586 | 0.803 | 0.892 | 0.687 | 0.368 |
| GT-ROI gated | RSICCformer | 0.858 | 0.807 | 0.877 | 0.833 | 0.015 |
| GT-ROI gated | Chg2Cap | 0.869 | 0.810 | 0.892 | 0.844 | 0.030 |
| MaskLabelOnly | RSICCformer | 0.890 | 0.825 | - | 0.870 | 0.188 |
| MaskLabelOnly | Chg2Cap | 0.895 | 0.827 | - | 0.874 | 0.222 |
| MGA-Hybrid | RSICCformer | 0.858 | 0.825 | 0.877 | 0.838 | 0.015 |
| MGA-Hybrid | Chg2Cap | 0.869 | 0.827 | 0.892 | 0.849 | 0.030 |

该pilot表明同一Claim—Evidence接口无需针对模型家族修改即可稳定处理两套独立真实输出。Hybrid相对Full target显著减少不可验证claim，并同时保留双时相Temporal分量；MaskLabelOnly的Overall更高主要来自不承担方向验证，不能据此判断其评价质量优于Hybrid。由于该子集没有逐描述人工正确性标签，上表只报告图像证据支持分布，不用于宣称MGA与人类判断的相关性，也不用于显著性模型排名。正式外部效度仍由独立盲化人工test承担。

## 4.10 变化问答适应性

`[已完成：补充材料，不承担主要结论]`

在40个SECOND-CC场景上，Qwen3-VL-2B自由回答频繁产生本体外或错误类别，导致Parser覆盖和精确转移准确率均为0。该结果说明小模型输出质量是端到端QA评价的上游瓶颈，不能用来宣称MGA已经在真实开放QA上获得成功。

在同一批场景构造的120条受控问答回答中，Q+A适配器在不改变MGA评分器的情况下得到：

| 方法 | Eval. Coverage ↑ | Neutral AUC ↑ | Balanced Acc. ↑ | FSR ↓ |
|---|---:|---:|---:|---:|
| GTClassLookup | 1.000 | 0.813 | 0.813 | 0.375 |
| MGA-Hybrid | 1.000 | **0.918** | **0.925** | **0.125** |
| OracleAllClass | 1.000 | 0.913 | 0.913 | 0.175 |

该实验只支持“同一个Claim验证器可以通过薄适配器处理QA形式”，不证明当前小模型具备可靠的遥感变化问答能力。更强QA模型属于后续扩展，不阻塞主论文。

## 4.11 本节总结

现有实验首先证明了MGA的核心计算逻辑：简单GT类别查找在标签不完整时发生可评分覆盖崩塌，纯开放词汇证据虽保持覆盖却受到分割噪声限制，而逐实体Hybrid路由能够在两者之间形成连续的准确性—覆盖折中。完整标注端Hybrid达到0.944 Neutral AUC和0.935 Balanced Accuracy，接近全类别Oracle；在隐藏类别条件下，Hybrid保持完整可评分覆盖，并相对纯开放证据取得稳定增益。

其次，人工pilot说明MGA不应被压缩为未经校准的单一Overall。MaskLabelOnly是标签范围内很强的空间基线，而Temporal是当前与人工事实判断最一致的视觉分量。因此，论文的主要贡献不是使用更复杂的分割模型取代GT，而是将可靠的空间/覆盖证据与开放的双时相方向证据组织成可诊断的验证流程。

最后，强风格改写和受控QA表明Claim—Evidence接口能够跨越表面句式和输入形式；RSICCformer与Chg2Cap的真实输出pilot进一步确认同一接口可以处理独立模型家族。Predicted-ROI、最小错误分解与Selective Prediction刻画了无测试GT部署、分量可诊断性和风险—覆盖折中。正式投稿的剩余外部效度主要取决于强统一评价基线和独立人工测试；这些未完成项仍保留明确占位，不会被提前写入主结论。

## 4.12 反向提纲

1. 4.1：定义四个研究问题并固定唯一主线。
2. 4.2：说明两个数据集的互补角色、证据路线和五项核心指标。
3. 4.3：用标注可用性曲线验证Hybrid主结论。
4. 4.4：用四路对照定位GT查找与开放分割的各自缺陷。
5. 4.5：用人工pilot说明分量式报告优于未经校准Overall。
6. 4.6–4.7：分析语言鲁棒性、Parser和视觉后端误差。
7. 4.8–4.9：用Predicted-ROI、最小错误分解和Selective Prediction限定部署边界。
8. 4.10：将QA限定为接口扩展。
9. 4.11：汇总已成立结论和仍待验证的外部效度。

## 4.13 Claim—Evidence 对照与自审

| 主要Claim | 当前证据 | 状态 |
|---|---|---|
| 参考文本匹配不能充分反映图像事实 | 强风格改写；传统指标下降而MGA保持 | 部分支持，待官方指标和独立等价标注 |
| Hybrid形成准确性—覆盖折中 | 64个标注子集、四路证据对照、阈值敏感性 | 已支持于受控SECOND-CC |
| Temporal提供独立的人类相关证据 | 三评审pilot中AUC 0.782 | 先导支持，待独立人工测试 |
| MGA优于强评价指标 | 尚无完整统一基线 | 待补实验 |
| MGA可在真实多模型输出上稳定工作 | RSICCformer/Chg2Cap各1000条；固定100场景、200条描述MGA pilot | 工程与分布层面已支持，待独立人工效度 |
| MGA可以在无测试GT时运行 | MCI/ChangeFormer Predicted-ROI；域内与跨域对照 | 部分支持，性能依赖变化检测器领域匹配 |
| LLM Parser提高开放表达处理能力 | 尚未独立评测 | 待补实验 |

自审：

- [x] 每个已完成数字均来自现有归档。
- [x] 明确区分Fact Coverage与Evaluation Coverage。
- [x] 不隐藏MaskLabelOnly在人工pilot中的强结果。
- [x] 不将GT-ROI版本称为完全无标注。
- [x] 不把受控QA写成真实开放QA成功。
- [x] 所有未完成实验均有显式占位。
- [ ] 补齐强指标和独立人工test后，完成RQ1的外部效度。
- [ ] 补齐独立人工测试后，完成RQ3的最终结论。
- [x] Predicted-ROI已完成；主张收窄为领域匹配且需开发集校准的无测试GT扩展。
