# MGA 方法与补充实验审稿式审计

日期：2026-07-27  
目标：检查新增方法章节、标注可用性曲线、QA/改写补充实验是否足以支撑当前论文主张。

## 1. 审计结论

当前材料已经足以支撑以下三项核心结论：

1. 评价开放式遥感变化语言不能只依赖参考句相似度，还需要验证实体、变化方向与空间关系是否具有双时相图像证据。
2. 纯 GT lookup 在类别不完整时会发生覆盖率崩塌，纯 OV 证据保留开放能力但判别性有限，逐实体 MGA-Hybrid 提供更合理的覆盖—准确性折中。
3. 在严格 Claim 等价条件下，MGA 对事实保持的句式和风格改写保持相同证据结果，而传统表面指标仍会下降。

当前材料尚不足以支撑以下强结论：

1. MGA 已经在真实开放变化问答输出上得到充分验证；
2. MGA-OV 已实现完全无标注部署；
3. Overall 是经过可靠校准的统一质量分数；
4. 当前方法已全面优于所有最新图文事实指标；
5. 人工评估已证明所有 MGA 分量都与人类判断高度一致。

## 2. Contribution

### Pass

- 将开放变化语言评价形式化为原子 Claim 与双时相证据的关联问题，而不是单图实体存在或参考文本匹配。
- 明确区分 MGA-GT、MGA-OV 和逐实体 MGA-Hybrid，并用 64 个标注子集给出连续使用条件。
- 报告 Spatial、Temporal、Fact Coverage、Context 和 Unverifiable，而不是只依赖单一 Overall。
- 引入事实图驱动的 factual/paraphrase/contradiction 协议，同时检查错误敏感性和改写鲁棒性。

### Needs revision

- 贡献描述应把“Hybrid 路由 + 双时相关系验证 + 分量式诊断”作为一个整体，避免被审稿人概括为简单的 GT/OV if-else。
- 标注曲线中低标注阶段 False Support Rate 上升是一项新的经验发现，应主动解释，而不是只报告最终提升。

## 3. Writing clarity

### Pass

- 中英文方法章节已经给出输入、Claim 表示、三种证据模式、Add/Remove/Modify、source-to-target 关系、状态阈值和聚合流程。
- QA 仅增加输入适配器，Qwen 不属于 MGA 核心方法，技术主线清楚。
- 摘要采用七句式，并明确 LEVIR-MCI 与 SECOND-CC。

### Needs revision

- 必须严格区分：
  - `Fact Coverage`：真实变化连通分量被文本证据覆盖的比例；
  - `Evaluation/Score Coverage`：样本获得数值评分的比例。
- `OracleAllClass` 是证据上界，不保证在当前二值/连续评分定义下取得最高 ROC-AUC。受控 QA 中 Hybrid AUC 略高于 Oracle，应在实验章节说明这是评分粒度差异，不是 Hybrid 证据比完整 GT 更准确。
- 所有阈值必须在实验设置中标明来源，尤其是 SegEarth 0.10、Supported 0.60 和 Contradicted 0.25。

## 4. Experimental strength

### Pass

- SECOND-CC：200 场景、600 条受控文本、六类全部 64 个标注子集。
- LEVIR-MCI：三评审 50 场景人工先导和真实 Draft/Change-Agent 风格改写。
- 标注可用性主曲线同时报告可评分覆盖、Neutral AUC、Balanced Accuracy、False Support Rate 和 Unverifiable Rate。
- 0.05/0.10/0.20 置信度敏感性已完成。
- 40 条强风格改写中 30 条 Claim 等价样本显示 MGA 不变、传统文本指标下降。

### Needs new experiment before final submission

1. 使用官方实现补齐 corpus BLEU、METEOR、ROUGE-L、CIDEr，最好增加 BERTScore 或 Sentence-BERT。
2. 在独立校准子集上选择 OV 置信度和关系阈值，不能以测试集曲线选参。
3. 计算各语义类别对曲线的边际收益，解释同一标注比例下较宽的 min–max 范围。
4. 若要把 QA 写成主要适用任务，需换用更强或遥感适配的 VLM，并获得非零 Parser 覆盖；当前 Qwen3-VL-2B 只能作为失败案例。
5. 与至少一到两个可复现的图像事实指标做公平比较；仅有文本指标和内部消融仍可能被认为 baseline 不完整。

## 5. Evaluation completeness

### 已完成

- GTClassLookup、OpenVocabOnly、Hybrid、OracleAllClass 四路证据对照；
- Full target、delta、GT-ROI、MaskLabelOnly、Hybrid 先导消融；
- Parser ontology/GLiNER/surface-form 分析；
- SegEarth 类别级定位误差；
- 三评审人工先导；
- 标注可用性曲线与阈值敏感性；
- QA 接口和风格鲁棒性小实验。

### 仍缺

- 统一标准传统指标表；
- 强图文事实指标；
- 类别边际贡献；
- 独立校准集；
- 更可靠的真实 QA 输出。

这些缺项不会推翻当前方法主线，但会影响 ACM MM 级别投稿的实验完整性。优先级建议为：标准指标/强 baseline > 独立校准 > 类别边际贡献 > 更强 QA 模型。

## 6. Method design soundness

### Pass

- Hybrid 逐实体回退符合真实“部分标注”场景；
- Unverifiable 避免把开放视觉检索失败直接等同于文本错误；
- QA 适配不改评分公式，避免为新任务另造指标；
- 0.05 与 0.10 曲线一致，显示结果对低置信度门槛有一定稳定性。

### Risk

- 当前受控 MGA-OV 使用语义变化 ROI，不能宣称完全无标注；
- SegEarth 在 SECOND-CC 上的 Add/Remove IoU 偏低，是低标注端性能瓶颈；
- False Support Rate 的低标注隆起说明混合 GT/OV 关系仍需校准；
- Claim 等价门控依赖 Parser，可能把 Parser 不认识的合法改写错误剔除；
- Overall 权重未独立校准，应继续作为补充结果。

## 7. 最终写作口径

主结论建议写为：

> MGA-Hybrid 通过逐实体组合可靠的封闭语义证据与可扩展的开放视觉证据，在标注可用性从纯 OV 到完整 GT 的连续条件下稳定提高事实判别能力，并同时改善可评分覆盖和不可验证率；其优势来自双时相关系证据，而不是简单查询 GT 类别是否存在。

语言鲁棒性建议写为：

> 对经规范 Claim 签名确认的事实保持改写，MGA 复用相同双时相证据并保持诊断结果，而基于有限参考的文本指标仍受到词汇和句法变化影响。

QA 适应性建议写为：

> MGA 的验证器可通过薄 Q+A 适配器复用于变化问答；受控回答验证了接口可行性，但 Qwen3-VL-2B 在真实开放回答中出现明显本体漂移，因此端到端 QA 效度仍待更强模型和人工标注验证。
