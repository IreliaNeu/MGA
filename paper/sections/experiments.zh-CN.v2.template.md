# 4 实验

> 合并稿 v2：自动实验数值由本地归档 JSON 生成；独立人工评价尚未完成。
> 本文档取代 v1 及两份实验增量稿作为后续实验写作入口。历史稿保留追溯。

## 4.1 研究问题与评价设置

本节检验 MGA-Hybrid 如何将双时相证据转化为变化描述的事实诊断。实验依次回答三个问题：可靠语义类别逐步可用时，实体级路由如何影响判别能力与可评分性；不同事实错误是否得到不同响应，以及这些响应与参考事实指标有何区别；同一验证流程在真实模型输出与不同感知条件下呈现怎样的支持度分布。独立人工评价将进一步检验这些诊断与人类事实判断的对应关系。

LEVIR-MCI/LEVIR-CC 对齐集承担真实输出评价：统一 1,000 对影像及 Draft、Refined、Change-Agent、RSICCformer、Chg2Cap 五组候选，共 5,000 条描述，每个场景绑定五条官方参考。Draft 与 Refined 按生成处理阶段区分，不计为两个独立模型家族。SECOND-CC 承担多类别受控验证：200 个场景的 600 条基础样本用于事实图与标注可用性分析；另以每场景一条事实描述和七类扰动构成 1,600 条错误诊断样本。不同实验使用各自的归档清单，不混合计算总体结果。[真实输出清单]({{source:manifest}})、[SECOND 基础实验]({{source:evidence}})、[错误诊断协议]({{source:errors}})。

MGA-Hybrid 是主方法，MGA-GT 提供完整语义证据条件，MGA-OV 检验开放视觉后端。GTClassLookup/MaskLabelOnly 是类别标签查询控制，不承担完整双时相关系验证。LEVIR 的 `hybrid_mask_temporal` 使用变化类别标签提供空间/coverage 证据，开放掩膜提供时相证据；SECOND 的 `known_gt_unknown_ov` 按实体路由双时相语义掩膜。两者体现相同的证据可用性原则，但原始标注能力和评分实现不同，因此分表报告。[LEVIR 汇总]({{source:unified}})、[SECOND 汇总]({{source:evidence}})。

本文分别报告 faithfulness、temporal、spatial/context support、fact coverage 与 unverifiable rate。Fact coverage 衡量描述覆盖已知变化事实的程度；evaluation coverage 衡量评价器能够赋予数值分数的样本比例。SECOND 表中的 U 为样本级不可评分率；真实描述表中的 U 遵循归档的 Claim 状态聚合。Neutral AUC 将不可评分样本映射为 0.5，该映射是统计约定，不改变 unverifiable 的语义。普通 BAcc 和 FSR 在可评分样本上计算，FSR 的分母为其中的负例；各表单独说明阈值。强基线表的 Oracle BAcc 使用该评测集上的最优阈值，仅作描述性上界。场景级置信区间依据对应汇总的 bootstrap 设置。[可评分性协议]({{source:availability}})、[强基线协议]({{source:external}})。

## 4.2 标注可用性与实体级证据路由

我们枚举 SECOND 六个类别的全部 64 个可用子集，对已标注实体采用语义证据，对其余实体采用开放掩膜。表 1 在每个可用类别数下对所有同规模子集取均值。开放证据要求 source 的 T1 掩膜、target 的 T2 掩膜非空且满足归档置信度门槛；因而评价器可以明确弃权，而非把感知缺失计为事实矛盾。

表 1：语义类别可用性与 MGA-Hybrid；BAcc 阈值为 0.5。

{{table:availability}}

随着可靠语义证据增加，Neutral AUC 与可评分覆盖率均提高。这支持以实体级路由利用部分标注，而不是为整句固定一个证据后端。FSR 在低标注阶段并不单调，因此类别可用性带来的判别收益不能解释为所有风险分量同步改善。

表 2 补充完整类别与隐藏类别条件下的四路对照。这里是早期无显式置信度弃权门控的关系实验，与表 1 的 verifiability 协议分开报告。该实验中的 MGA-OV 仍使用 GT 变化 ROI；MGA-GT 对应归档的 `oracle_all_class` 实现。不同路径的数值不能当作完全相同算子下的严格单调上界。

表 2：四路证据控制；BAcc 阈值为 0.5，`open_set` 隐藏 tree、low vegetation、water。

{{table:routes}}

隐藏类别时，GTClassLookup 只覆盖其能够查询的部分样本；Hybrid 保留开放回退并验证局部 source-to-target 关系。该对照将证据可用性与事实判断能力分别显式化。

## 4.3 最小事实错误与强事实指标

每类扰动改变一个预定事实因素，包含方向、实体、额外幻觉、位置、no-change、遗漏与关系。表 3 使用归档的 `diagnostic_score = evidence_score × atomic_fact_coverage`，其中后者依赖受控事实图。Strict pair accuracy 要求正确描述严格高于错误描述，并列不计成功。扰动的人工有效性复核尚未完成，因此当前结果描述的是构造协议下的行为。

表 3：MGA-Hybrid 对七类错误的响应，每类 200 对对照；BAcc/FSR 阈值为 0.5。

{{table:errors}}

方向、实体、关系及 no-change 的判别表现与预期诊断目标一致；位置和额外幻觉给出较高的 false support rate，定位了需要进一步验证的局部证据问题。遗漏诊断的依据是事实图覆盖率；该结果不支持把未表达事实的识别归因于 reference-free evidence score。

在相同的 1,600 条样本上，ALOHa-local 采用 SpaCy-small、MPNet 与官方 local variant 的对象匹配；FMScore-Qwen 保留事实 yes/no 协议，并用 Qwen3-VL-2B 替代原后端。它们是明确标注实现边界的比较设置。

表 4：受控事实判别；2,000 次场景 bootstrap，seed=20260813。

{{table:external}}

{{table:deltas}}

MGA-Hybrid 相对 ALOHa-local 的配对 AUC 差异区间为正；相对 FMScore-Qwen 的区间跨零，现有结果未建立总体 AUC 优势。本文关注候选 Claim 的双时相验证及分量诊断；是否在真实描述上为强指标提供额外有效信息，将由独立人工测试检验。

## 4.4 真实多模型输出与参考指标

五组真实候选共用相同评价流水线，表 5 展示其证据支持度分布。Overall 保留为历史实现的补充汇总，主解释采用分量。由于这些描述尚无完整独立人工标签，表中顺序不作为生成模型准确率排名。

表 5：1,000 对影像上的 MGA-Hybrid 分量与 Parser 无 Claim 比例。

{{table:unified}}

Refined 的无 Claim 比例高于其余系统，因此其低分需要与 Parser 覆盖共同解释。后续 Oracle Claim 消融将固定视觉证据，只替换解析结果，定位误差传播。

参考指标在对齐场景上重新计算 Draft/Refined；其他模型原论文的数值不混入同场景比较。下表同时列出核心参考指标、语义指标和复合指标。CLIP 为 T1/T2 单图余弦相似度的均值，不显式建模方向。

表 6：同场景、同参考设置下的参考文本指标。

{{table:text}}

{{table:semantic_text}}

表 7：指标间相关性及有效样本数。

{{table:correlations}}

Temporal 与参考指标呈现不同于 Overall 的关联结构；两种 MGA 分量的有效样本数也不同。该观察提出“时相证据提供补充信息”的验证假设，不能单凭较低相关性证明人工效度或增量价值。

## 4.5 感知条件、Parser 与选择性

ROI 实验固定 97 个 development 场景和 103 个 test 场景，阈值由前者选择。表 8 报告 Hybrid 路径的 test 结果。Predicted-CD 使用跨域 ChangeFormer 变化证据，No-ROI 与 GT-ROI 提供门控对照。

表 8：开发集校准后的 Hybrid ROI 对照。

{{table:roi}}

预测 ROI 在当前设置下减少错误支持，但没有提高总体 Neutral AUC；其作用应结合领域匹配和风险目标解释。此表的 Hybrid 仍使用可用类别语义证据，不代表整个方法已无标注部署。

表 9 在固定 500 场景、2,500 条描述上比较 Grounding DINO Tiny/Base；框阈值 0.30、文本阈值 0.25、查询与 Claim 保持一致。Base 的分量变化体现定位保守性与可验证性之间的折中，不能据此改变先前 SegEarth 主实验的后端身份。

{{table:dino}}

表 10 将基础本体与补充 surface-form 配置后的 Parser 分开。配置化本体对这组 1,200 条受控样本的高覆盖检验的是词表覆盖能力；它不替代真实开放表达上的独立 Claim 标注。

{{table:parser}}

选择性实验按视觉置信度保留样本，并在边界包含全部同置信度项，因此实际 coverage 可以高于请求值。表 11 同时报告 supported precision，避免只用类别不平衡条件下的准确率评价选择性收益。曲线属于归档数据上的描述性分析，部署阈值仍需独立固定。

{{table:selective}}

表达鲁棒性作为补充机制分析：50 条改写中 72% 通过 canonical Claim 等价门控，通过者状态一致率为 1、平均分差为 0。结论限定为确认 Claim 等价后的不变性。自由 QA 的 40 条回答在 Parser 成功率、精确转移与 Hybrid coverage 上均为 0，保留为接口扩展记录，不承担主要结论。[改写与 QA 汇总]({{source:qwen}})。

## 4.6 人工效度：pilot 与独立测试

历史 pilot 包含 50 场景和三名评审，是探索性分析。文本对齐后 149/150 条候选匹配，49 个场景完整；一条 Refined 文本与评分清单不一致。表 12 显式列出有效样本数，避免把不同覆盖范围的 AUC 直接解释为配对优势。[匹配记录]({{source:human}})。

{{table:pilot}}

偏好题 Fleiss κ 为 0.315；GT 漏标题的一致性为负。正式协议将事实正确、证据不足、不适用和 GT 覆盖审计分开，保留仲裁前的评审分歧。[三评审记录]({{source:raters}})。

**独立人工效度未完成。** 用户拟组织约五名评审、约 200 条样本，样本是否指影像对及最终候选分配尚待确定。本稿不填入模拟人工结果。标注完成后，主比较采用同场景、同候选、同人工维度的指标配对分析，报告 AUC、固定阈值 BAcc、Spearman/Kendall、场景内 pairwise accuracy、评审一致性及场景 bootstrap 区间。若拟合组合指标或选择阈值，仅使用 development；test 不参与选择。

## 4.7 实验结论

现有实验支持 MGA-Hybrid 用实体级证据路由组织部分语义标注与开放感知，并以双时相 Claim 验证呈现事实错误的分量差异。真实输出、ROI 和后端对照进一步表明，评价器应同步报告证据来源、Parser 覆盖及 unverifiable 状态。独立人工测试将决定这些诊断与人类事实判断的对应强度，以及它们对参考文本和事实基线的增量价值。
