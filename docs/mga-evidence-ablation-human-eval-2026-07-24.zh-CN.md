# MGA 证据构造消融与人工评价审计

日期：2026-07-24

## 1. 审计结论

当前人工评价表**有用，但只够作为先导实验，不足以作为论文最终人工评价**。

本轮最重要的实证结论是：

1. `MaskLabelOnly` 在人工“变化描述是否成立”上的区分能力不弱于当前
   SegEarth 空间分数：
   - `MaskLabelOnly Faithfulness`：ROC-AUC = 0.569；
   - `Full target Faithfulness`：ROC-AUC = 0.374；
   - `MaskLabelOnly Coverage`：ROC-AUC = 0.572；
   - `Full target Coverage`：ROC-AUC = 0.567。
2. 不能因此完全移除 SegEarth。`Temporal` 单项仍是本轮最有效的自动证据：
   ROC-AUC = 0.785，Balanced Accuracy@0.60 = 0.728，但只有 93 条可计算
   caption。
3. 当前 `Overall` 不具备良好的人类效度：
   - `Full target Overall`：ROC-AUC = 0.417；
   - `Temporal delta Overall`：ROC-AUC = 0.415；
   - `GT-ROI gated Overall`：ROC-AUC = 0.466；
   - `MaskLabelOnly Overall`：ROC-AUC = 0.555。
4. `GT-ROI gated` 使用真实变化 ROI，明显抬高 Faithfulness、降低
   Unverifiable，但没有带来可靠的人类效度，应只作为带 oracle 信息的乐观对照。
5. `Temporal delta` 没有解决当前问题。它改变空间支持和覆盖掩膜，但现有
   Temporal 公式不变，因此 Temporal 结果与 Full target 相同。

建议把主方法改成可解释的分量式设计：

- 类别存在与覆盖：`MaskLabelOnly`；
- 时相方向：SegEarth 的 `Temporal`；
- 不再用当前 0.65/0.35 权重强行合成未经验证的 Faithfulness；
- 主文报告分量向量，标量 Overall 仅作为次要汇总。

## 2. 人工评价表分析

### 2.1 原始结果

有效场景数为 50，只有 1 名专家。

| 指标 | 正例/选择数 | 比例 |
|---|---:|---:|
| Change-Agent 描述成立 | 36/50 | 0.72 |
| Draft 描述成立 | 36/50 | 0.72 |
| Refined/Guided 描述成立 | 34/50 | 0.68 |
| Refined 新增了正确细节 | 34/50 | 0.68 |
| 正确定位但 GT Mask 未标 | 14/50 | 0.28 |
| 人工偏好 Refined | 27/50 | 0.54 |
| 人工偏好 Draft | 18/50 | 0.36 |
| 人工偏好 Change-Agent | 5/50 | 0.10 |

Draft 与 Refined 的“描述成立”并无显著差异。配对结果为：

- Draft=0、Refined=1：11 条；
- Draft=1、Refined=0：13 条；
- McNemar 精确检验：`p = 0.839`。

人工与表中 LLM-as-Judge 的完全一致率为 0.48，Cohen's κ = 0.113。
这只能说明两者一致性较弱，且两列的候选集合并不完全相同，不能把 LLM 判断
当成人工标注替代品。

### 2.2 表格质量问题

1. 底部 K/L 列手工汇总与 50 行原始数据不一致：
   - K 列原始数据实际为 Refined=27、Draft=18、Change=5；
   - L 列原始数据实际为 Refined=25、Draft=20、Tie=5。
2. F/G/H 只判断“变化物体是否成立”，没有区分：
   - 实体类别；
   - Add/Remove/Modify 方向；
   - 位置；
   - 数量；
   - 属性；
   - 多实体 caption 中哪一个实体出错。
3. I 列只询问 Refined 是否新增正确细节，没有对 Draft 和 Change-Agent
   做对称提问，因此天然偏向 Refined。
4. J 列很重要，但“模型定位出的物体”没有记录具体模型、实体和证据区域，
   无法据此修正 GT 或判断是 GT 漏标还是模型误检。
5. K 列“更想看哪条描述”混合了事实正确性、信息量、流畅性和个人偏好，
   不能直接作为 MGA 正确性标签。
6. Caption 顺序和模型身份没有盲化，可能存在顺序与模型标签偏差。
7. 只有 1 名专家，不能计算人工标注者间一致性。
8. 服务器 manifest 与人工表 150 条 caption 中有 149 条语义对齐；
   `levir-cc_test_000217/Guided` 存在真实文本版本差异：
   `previously undeveloped area` 与 `vegetated area`。

### 2.3 建议的最终人工评价协议

每条 caption 先由 Parser 拆为原子 claim，然后按 claim 标注：

| 维度 | 推荐标注 |
|---|---|
| 实体类别 | 正确 / 错误 / 无法判断 |
| 变化方向 | Add / Remove / Modify / No-change 是否正确 |
| 空间位置 | 0=错误，1=部分正确，2=正确 |
| 数量/属性 | 正确 / 错误 / 未提及 |
| GT 漏标 | 无 / 疑似 / 明确，并记录实体类别 |
| 整句事实性 | 1–5 分 |
| 信息完整性 | 1–5 分 |
| 语言流畅性 | 1–5 分 |
| 总体偏好 | 可选，不能替代上述维度 |

论文最低建议：

- 至少 2 名标注者，最好 3 名；
- 盲化模型名称并随机化 caption 顺序；
- 100–200 个场景，按 no-change、building、road、混合变化和困难案例分层；
- 二值题报告 Cohen/Fleiss κ，序数题报告 weighted κ 或 Krippendorff's α；
- 对分歧样本进行仲裁，但同时保留仲裁前一致性；
- 报告 95% 置信区间，不只报告均值；
- 将本轮 50 条作为 pilot/dev，不再用作最终独立测试集。

## 3. 已完成的证据构造

代码中新增四种 `EvidenceMode`：

| 模式 | 定义 | SegEarth |
|---|---|---|
| `full_target` | Add=post，Remove=pre，Modify=pre∪post | 需要 |
| `temporal_delta` | Add=post-pre，Remove=pre-post，Modify=pre XOR post | 需要 |
| `gt_roi_gated` | 先用对应类别 GT ROI 门控 pre/post | 需要，且使用 oracle |
| `mask_label_only` | Parser 的 road=1、building=2 直接匹配 GT 类别 | 不需要 |

本轮运行了两组对照：

- 开发集：100 场景 × 3 caption；
- 人工效度集：50 场景 × 3 caption。

人工效度集的分模型均值如下：

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| Full | Change-Agent | 0.700 | 0.863 | 0.872 | 0.767 | 0.130 |
| Full | Draft | 0.632 | 0.837 | 0.775 | 0.708 | 0.130 |
| Full | Guided | 0.366 | 0.507 | 0.508 | 0.399 | 0.220 |
| Delta | Change-Agent | 0.737 | 0.853 | 0.872 | 0.784 | 0.180 |
| Delta | Draft | 0.665 | 0.825 | 0.775 | 0.723 | 0.150 |
| Delta | Guided | 0.391 | 0.485 | 0.508 | 0.406 | 0.210 |
| GT-ROI | Change-Agent | 0.907 | 0.863 | 0.872 | 0.878 | 0.040 |
| GT-ROI | Draft | 0.832 | 0.837 | 0.775 | 0.816 | 0.040 |
| GT-ROI | Guided | 0.546 | 0.507 | 0.508 | 0.488 | 0.120 |
| MaskLabelOnly | Change-Agent | 0.918 | 0.865 | - | 0.889 | 0.130 |
| MaskLabelOnly | Draft | 0.847 | 0.839 | - | 0.833 | 0.123 |
| MaskLabelOnly | Guided | 0.567 | 0.509 | - | 0.510 | 0.190 |

注意：MaskLabelOnly 没有 Temporal，Overall 会对剩余可用权重重新归一化，
其绝对值不能与其他模式直接比较。

人工50场景 SegEarth 推理耗时 68.99 秒，峰值显存 5408.5 MiB。

## 4. 当前 MGA 的计算过程

### 4.1 Parser 与类别 ROI

Caption 被拆成原子 claim：

`(entity, role, change_type, location, count, attributes, target_labels)`。

当前主要类别映射：

- road → label 1；
- building/house/villa/structure → label 2。

对实体 `e`，真实类别变化 ROI 为：

`R_e = [Y ∈ target_labels(e)]`

其中 `Y` 是多类 GT Mask。

### 4.2 Full target 时相证据

令 SegEarth 在 A/B 时相的实体掩膜分别为 `P_e` 和 `Q_e`：

- Add：`Target=Q_e`，`Other=P_e`；
- Remove：`Target=P_e`，`Other=Q_e`；
- Modify/Unknown：`Target=P_e ∪ Q_e`。

### 4.3 Claim 级空间分数

当前空间支持使用预测支持的精确率：

`Spatial = |Target ∩ R_e| / |Target|`

若 Target 为空或目标时相置信度低于 0.25，则该 claim 为
`Unverifiable`，不赋连续 Faithfulness。

### 4.4 Claim 级时相分数

Add/Remove：

`Temporal = 1 - |Target ∩ Other ∩ R_e| / |Target ∩ R_e|`

Modify：

`Temporal = |(P_e XOR Q_e) ∩ R_e| / |(P_e ∪ Q_e) ∩ R_e|`

### 4.5 Claim Faithfulness 与状态

若 Spatial 和 Temporal 均可用：

`Faithfulness = 0.65 × Spatial + 0.35 × Temporal`

状态不是只看加权均值，而是逐轴判断：

- 任一可用轴 ≤ 0.25：`Contradicted`；
- 所有可用轴 ≥ 0.60：`Supported`；
- 其他情况：`Unverifiable`。

No-change claim 直接检查目标类别变化 Mask 是否为空。

Context claim 目前只用实体存在置信度，不再因其与变化区域重叠而自动惩罚。

### 4.6 Coverage

先将所有 changed claim 的支持掩膜求并集。对 GT 变化 Mask 做 4 邻域连通域
分解，忽略面积小于 4 像素的分量。若某 GT 分量至少 10% 被支持并集覆盖，
则该分量算 covered：

`Coverage = covered_components / all_components`

### 4.7 Caption 级汇总

- Faithfulness：可验证 changed/no-change claim 的平均值；
- Temporal：可计算 Temporal claim 的平均值；
- Context Support：可验证 context claim 的平均值；
- Unverifiable Rate：Unverifiable claim 数 / 全部 claim 数；
- Overall：

`Overall = 0.55 × Faithfulness + 0.25 × Coverage + 0.20 × Temporal`

当某一分量不可用时，代码会按剩余可用权重重新归一化。因此必须同时报告原始
分量和缺失率，不能只报告 Overall。

## 5. 是否满足论文写作要求

### 当前可以写的内容

- 问题定义：传统文本指标不能直接验证变化实体的空间与时相依据；
- MGA 的原子 claim、类别 ROI、空间/时相/覆盖分量定义；
- Parser、同义词映射、SegEarth 接入和可视化流水线；
- Full/Delta/GT-ROI/MaskLabelOnly 的方法消融；
- 一个重要负结果：复杂分割空间证据没有优于简单类别基线；
- 一个正结果：时相分量与人工事实判断有初步一致性。

### 当前还不能稳健宣称的内容

- 不能宣称 Overall 已被人工验证；
- 不能宣称 SegEarth 整体优于简单基线；
- 不能宣称 Refined/Guided 整体优于 Draft；
- 不能把单专家50条作为最终人类评价；
- 不能把 GT-ROI gated 当作可部署方法；
- 未完成系统文献审计前，不能宣称该指标达到 SOTA 或具有充分方法新颖性。

当前项目更适合定位为：

> 面向遥感变化描述的可解释诊断指标与实证分析，而不是新的遥感分割模型。

## 6. 后续最高优先级

1. 实现并验证 Hybrid：
   - Spatial/Coverage = MaskLabelOnly；
   - Temporal = SegEarth；
   - 不直接复用当前 Overall 权重。
2. 修复 `levir-cc_test_000217/Guided` 的 caption 版本一致性。
3. 重新设计人工表，先让第2名专家复标当前50条，验证协议和一致性。
4. 新选独立 held-out 100–200 场景，不与当前调参集重复。
5. 在 held-out 集上报告：
   - ROC-AUC、Balanced Accuracy、相关系数；
   - bootstrap 95% CI；
   - Full 与 MaskLabelOnly/Hybrid 的配对差异；
   - 每实体、每变化类型、no-change 分层结果。
6. 人工标注 20–30 个场景的时相实体掩膜，区分：
   - Caption 错误；
   - Parser 错误；
   - SegEarth 分割错误；
   - GT Mask 漏标；
   - 跨时相配准抖动。
7. 补充效率表：推理时间、峰值显存、模型依赖和缓存后评分成本。

停止条件：

- 若 Hybrid 的 Temporal 在独立测试集上相对 MaskLabelOnly 没有置信区间意义上的
  增益，则主方法简化为 MaskLabelOnly 诊断指标；
- 若 Temporal 的优势可复现，则保留 SegEarth 作为独立时相证据模块，而不是
  作为整个 MGA 的必要前提。

## 7. 服务器与本地结果位置

服务器：

- 100场景证据消融：
  `/root/autodl-tmp/mga-artifacts/ablations/evidence-mode-100x3-v1`
- 人工50场景 SegEarth：
  `/root/autodl-tmp/mga-artifacts/segearth-ov3/human-eval-50x3-v1`
- 人工50场景证据消融与对齐：
  `/root/autodl-tmp/mga-artifacts/ablations/evidence-mode-human-50x3-v1`
- 人工50场景 manifest：
  `/root/autodl-tmp/datasets/organized/mga_levir_mci_1000/manifests/human_eval_50x3_claims_v4.jsonl`

本地只保存 summary 和 Markdown 总览，不保存逐条分数、分割掩膜或场景图。
