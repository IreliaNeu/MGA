# MGA 面向 ACM MM 的后续工作清单

> **历史清单提示（2026-09-06）：** 本文件记录 7 月规划，多个 P0 项已经完成。当前状态与剩余任务以 `mga-acmmm-next-work-checklist-2026-08-12-supplement.zh-CN.md` 和 `project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md` 为准。

日期：2026-07-27  
主目标：ACM MM  
强化目标：CVPR  
当前主方法：MGA-Hybrid

## 1. 论文唯一主线

本文不把重点放在生成更流畅的变化描述，而是研究如何评价开放式遥感变化语言是否忠实于双时相图像。完整论证链为：

> 参考文本指标只能衡量候选句与有限参考表达的相似性，无法直接验证实体、变化方向和局部转换关系；MGA 将文本分解为原子变化 Claim，并为每个 Claim 构造双时相视觉证据；MGA-Hybrid 对已有语义类别使用可靠标注，对标签外实体回退到开放词汇证据，在部分标注条件下形成可解释的准确性—覆盖折中；人工判断、最小错误扰动和标注可用性曲线共同验证该证据链。

主文只保留三项核心贡献：

1. **问题与定义：** 将遥感变化语言评价从参考文本匹配重新定义为原子 Claim 的双时相证据验证。
2. **方法：** 通过实体级 Hybrid 路由、Add/Remove/Modify 和 source-to-target 关系证据，分别诊断 Spatial、Temporal、Fact Coverage 与 Verifiability。
3. **实证：** 在真实模型输出和多类别受控样本上验证错误敏感性、表达鲁棒性以及随标注可用性变化的准确性—覆盖折中。

QA、小模型生成、LLM Parser 和新的开放变化检测器均为支持模块或扩展实验，不单独构成论文主线。

## 2. P0：投稿前最应该完成

### P0-1 多模型真实输出与统一评价基线

- [x] 在 LEVIR-MCI/LEVIR-CC 对齐测试集上生成 RSICCformer 输出（1000条，清单审计通过）。
- [x] 在相同测试集上生成 Chg2Cap 输出（1000条，清单审计通过）。
- [x] 保留已有 Change-Agent、Draft 和 Refined 输出，并在统计中将其标记为同一模型家族的不同阶段。
- [ ] 建立统一 `sample_id / model_family / model_variant / caption / provenance` 清单。
- [ ] 对全部候选输出运行同一版本的 MGA Parser、证据缓存和评分配置（RSICCformer/Chg2Cap固定100场景pilot已完成；全候选统一表仍待补）。
- [ ] 使用官方实现补齐 BLEU-1/4、METEOR、ROUGE-L、CIDEr、SPICE 和 BERTScore。
- [ ] 增加至少一个图文基线，例如 CLIPScore 或 RemoteCLIPScore。
- [ ] 增加至少一个事实评价基线，优先选择能够稳定复现的 FMScore、ALOHa 或 InfoMetIC。
- [ ] 保留 MaskLabelOnly、MGA-GT、MGA-OV、MGA-Hybrid 和 Oracle 作为内部证据路线。
- [ ] 报告样本级相关性与成对排序，不只报告各模型平均分排名。

**验收输出：**

- `model_outputs_manifest.jsonl`
- `metric_baseline_summary.json`
- 主文“自动指标与人工判断一致性”表
- 每个模型家族的 Parser 覆盖率和 Unverifiable Rate

### P0-2 独立人工效度实验

- [ ] 新增 80–100 个未用于当前阈值选择的场景。
- [ ] 每个场景评价 3 条候选描述，覆盖不同生成模型和难度。
- [ ] 使用 3 名评审，模型身份盲化，Caption 顺序随机化。
- [ ] 先按 Claim 标注实体、方向、位置、关系和证据充足性。
- [ ] 再分别标注整句事实性、信息完整性和语言流畅性。
- [ ] 允许 `Supported / Contradicted / Insufficient evidence` 三值判断。
- [ ] 使用 10–15 个场景统一标注指南，但不把该试标集计入最终结果。
- [ ] 报告 Fleiss κ 或 Krippendorff's α、场景级 bootstrap 95% CI。
- [ ] 报告 MGA 各分量与对应人工维度的 AUC、Balanced Accuracy、Spearman/Kendall 和 pairwise accuracy。
- [ ] 将当前 50 场景三评审结果保留为 pilot，不与新测试集混合调参。

**验收条件：**

- 核心事实性题的一致性至少达到可解释的中等水平；
- Temporal 与人工方向判断保持显著关联；
- Hybrid 在标签外或方向错误子集上相对 MaskLabelOnly 显示稳定增益；
- 若 Overall 不能稳定优于分量，不再将 Overall 作为主结果。

### P0-3 最小错误类型分解

- [ ] 从现有正确描述构造错误实体。
- [ ] 构造 Add/Remove 方向颠倒。
- [ ] 构造错误空间位置。
- [ ] 构造错误 source-to-target 关系。
- [ ] 构造虚构额外变化。
- [ ] 构造遗漏真实变化。
- [ ] 构造 no-change 误报。
- [ ] 可选增加数量/属性错误。
- [ ] 每次只修改一个 Claim 字段，保持句法和长度尽可能一致。
- [ ] 对至少 10%–20% 扰动进行人工有效性核验。
- [ ] 分错误类型报告检测 AUC、pairwise accuracy、FSR 和 U。

**验收目的：** 证明 Spatial、Temporal、Coverage 和 Verifiability 各自对应可区分的错误，而不是任意拆分出的分数。

### P0-4 去除 OV 对测试 GT-ROI 的隐含依赖

- [ ] 将现有模式明确重命名为 `MGA-OV + Oracle GT-ROI`。
- [ ] 使用固定的预测变化概率图构造 `MGA-OV + Predicted ROI`。
- [ ] 优先复用已有变化检测输出；所有 Caption 模型共享同一张场景级预测 ROI。
- [ ] 增加 DINOv2/双时相特征差分 ROI 作为弱监督压力测试。
- [ ] 增加 No-ROI 版本。
- [ ] 使用软门控而不是只做硬二值交集，减少变化检测漏检导致的证据清零。
- [ ] 在验证集选择 ROI 阈值，在测试集固定。
- [ ] 同时报告 ROI IoU/F1 和下游 MGA 指标，量化 Oracle gap。

**论文决策：**

- 若 Predicted-ROI 明显优于 No-ROI 和强基线，可将其写为可部署版本；
- 若 Predicted-ROI 有下降但仍具判别力，将其写为感知瓶颈与现实折中；
- 若 Predicted-ROI 接近随机，则主张收窄为“部分标注辅助的证据评价器”，不宣称完全无标注部署。

### P0-5 Parser 级联与独立评测

- [ ] 保留规则/配置词表作为高精度第一层。
- [ ] 只对未命中或歧义片段调用本地 LLM。
- [ ] 使用固定 JSON Schema 输出实体、方向、角色、位置、关系和置信度。
- [ ] 允许 `open_entity` 和 `unknown`，禁止强制映射为 building/road。
- [ ] 固定模型、prompt、temperature、权重哈希并缓存输出。
- [ ] 对比 Rule-only、LLM-only、Rule+LLM fallback 和 Oracle Claim。
- [ ] 在真实多模型输出、人工改写、否定表达和最小错误样本上评测。
- [ ] 报告 entity span F1、规范化准确率、方向 macro-F1、关系 exact match、abstention rate 和运行成本。
- [ ] 不使用同一个 LLM 同时生成改写和判断改写是否等价。

**停止条件：** 若 LLM fallback 不能提高真实文本上的召回，或显著降低精确率，则 Rule-only 继续作为主 Parser，LLM 结果进入补充材料。

### P0-6 独立校准与统计

- [ ] 将人工数据划分为 development/test，test 不参与阈值和权重选择。
- [ ] 校准 OV 置信度、Supported/Contradicted 阈值和 ROI 阈值。
- [ ] Overall 权重仅在 development 上拟合；若不稳定则删除主文 Overall。
- [ ] 对所有主要比较使用场景级 paired bootstrap。
- [ ] 对类别不平衡结果同时报告 macro 与 micro 统计。
- [ ] 明确区分 Fact Coverage 与 Evaluation Coverage。

## 3. P1：强烈建议完成

- [ ] 计算 SECOND-CC 各语义类别对标注可用性曲线的边际收益。
- [ ] 增加实例漏标、像素缺失、边界噪声和类别错误，模拟真实不完整标注。
- [ ] 分析配准偏移、膨胀半径和关系半径的敏感性。
- [ ] 至少比较两个变化 ROI 后端或两个开放词汇证据后端。
- [ ] 按 building/road、目标大小、变化方向和场景复杂度进行分层。
- [ ] 报告每场景推理时延、峰值显存、缓存体积和批量运行成本。
- [ ] 按预先声明规则选择成功、失败和 Unverifiable 案例。
- [ ] 将主文表格转换为 booktabs 风格，并统一指标方向、有效位数和置信区间格式。

## 4. P2：次要或后续扩展

- [ ] 更强遥感 VLM 的真实开放变化问答。
- [ ] 更大规模的 QA 评价集。
- [ ] 数量、属性、相对空间关系和复杂共指解析。
- [ ] 完全无监督变化 ROI。
- [ ] 更多遥感或自然图像变化描述数据集。
- [ ] 训练专用 Parser 或端到端证据校准器。
- [ ] 将 MGA 扩展为通用 bi-temporal grounded language evaluation benchmark。

P2 不应阻塞 ACM MM 投稿。若以 CVPR 为目标，则 Predicted-ROI、跨后端泛化、更大人工基准和更一般的双时相任务定义应提升为 P0/P1。

## 5. 推荐执行顺序

1. 本地完成最小错误扰动生成、数据核验和人工表设计。
2. 启动服务器，运行 RSICCformer 与 Chg2Cap，生成统一候选输出。
3. 一次性缓存 building/road 开放分割和预测变化 ROI。
4. 运行统一指标基线、ROI 对照和 Parser 消融。
5. 冻结阈值与实验配置。
6. 开展独立人工评价。
7. 计算统计显著性、错误分层和失败案例。
8. 固化论文主表、主图和补充材料。
9. 根据 Predicted-ROI 和人工效度结果决定最终主张范围。

## 6. 当前可以写入与必须留空的内容

### 已有证据，可直接写入

- Hybrid 标注可用性曲线；
- 四路证据对照；
- Parser 受控 surface-form 实验；
- SegEarth 类别级定位分析；
- 三评审 50 场景 pilot；
- 强风格改写与受控 QA；
- 阈值敏感性和场景级 bootstrap。

### 必须标记为待补

- RSICCformer/Chg2Cap 真实输出结果；
- 完整传统与图文评价基线；
- 独立 80–100 场景人工效度；
- Predicted-ROI 正式结果；
- LLM Parser 独立基准；
- 多错误类型正式主表。

## 7. 投稿前停止条件

出现以下任一情况时，应收窄主张而不是继续堆叠模块：

1. Hybrid 在独立人工集上不优于简单基线，也不能在方向或标签外子集展示独立价值；
2. Predicted-ROI 完全失效且论文仍试图宣称无标注部署；
3. Parser 在真实多模型输出上覆盖率过低，导致大量结果无法评分；
4. MGA 与人工判断的相关性不高于传统或图文强基线；
5. 主要增益只能在由同一 GT 构造和验证的受控文本中出现。

若上述风险发生，保留仍成立的结论：MGA 是一个分量式、标注辅助的双时相事实诊断框架，并把无标注与开放 QA 降级为未来工作。
