# 三评审人工评价与 Hybrid 50 场景实验总结

## 1. 数据与统计口径

- 使用 `human evla_filled_1/2/3.xlsx` 的第 2–51 行，共 50 个场景、3 名评审。
- 不采用工作簿底部手工汇总，所有比例均由原始标注重新计算。
- 二值题使用三人多数票；偏好题有 2 个场景三人未形成多数，记为 `NoMajority`。
- 第三份评审的“GT 掩膜是否漏掉正确实体”有 1 个空值；该题的 Fleiss κ 使用 49 个完整案例。
- 自动指标对齐 149/150 条 caption。唯一排除项为 `levir-cc_test_000217` 的 Refined
  文本版本不一致（“previously undeveloped area”与“vegetated area”）。

## 2. 三评审一致性

| 题目 | 三人完全一致率 | Fleiss κ | 多数票正例 |
|---|---:|---:|---:|
| Change-Agent 描述正确 | 0.620 | 0.418 | 31/50（0.620） |
| Draft 描述正确 | 0.700 | 0.524 | 34/50（0.680） |
| Refined 描述正确 | 0.740 | 0.606 | 36/50（0.720） |
| Refined 新增细节正确 | 0.460 | 0.272 | 28/50（0.560） |
| 正确实体未被 GT 掩膜覆盖 | 0.122 | -0.171 | 16/50（0.320） |
| 三描述偏好 | 0.460 | 0.315 | Refined 31，Draft 15，Tie 2，无多数 2 |

人工多数票与 LLM-as-Judge 在 48 个有有效多数票的场景上完全一致率为 0.667，
Cohen κ 为 0.372。

关键判断：

1. “Refined 是否整体正确”具有当前最高的可复现性，可作为第一版表中最可信的主标签。
2. “新增细节是否正确”和主观偏好只有较弱至一般的一致性，需要更明确的边界、示例和错误类型定义。
3. “GT 是否漏标”当前不可作为论文主结论。第三位评审给出 40/49 个正例，而前两位仅为
   14/50 和 17/50，说明评审口径并不一致；应先统一“实体类别存在”“空间定位正确”和
   “GT 变化掩膜未覆盖”的定义，再重新标注或仲裁。

## 3. 完整 50 场景证据消融

### 3.1 自动分数概览

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| Full target | Change-Agent | 0.700 | 0.863 | 0.872 | 0.767 | 0.130 |
| Full target | Draft | 0.632 | 0.837 | 0.775 | 0.708 | 0.130 |
| Full target | Refined | 0.366 | 0.507 | 0.508 | 0.399 | 0.220 |
| MaskLabelOnly | Change-Agent | 0.918 | 0.865 | — | 0.889 | 0.130 |
| MaskLabelOnly | Draft | 0.847 | 0.839 | — | 0.833 | 0.123 |
| MaskLabelOnly | Refined | 0.567 | 0.509 | — | 0.510 | 0.190 |
| Hybrid | Change-Agent | 0.907 | 0.865 | 0.872 | 0.879 | 0.040 |
| Hybrid | Draft | 0.832 | 0.839 | 0.775 | 0.816 | 0.040 |
| Hybrid | Refined | 0.546 | 0.509 | 0.508 | 0.489 | 0.120 |

### 3.2 与三评审多数票的对齐

| 模式/指标 | n | ROC-AUC | Balanced Acc@0.60 |
|---|---:|---:|---:|
| Full / Overall | 149 | 0.466 | 0.584 |
| MaskLabelOnly / Overall | 149 | 0.593 | 0.644 |
| Hybrid / Overall | 149 | 0.512 | 0.639 |
| Full / Faithfulness | 142 | 0.448 | 0.457 |
| MaskLabelOnly / Faithfulness | 142 | 0.625 | 0.612 |
| Hybrid / Faithfulness | 142 | 0.519 | 0.612 |
| Full 或 Hybrid / Temporal | 93 | 0.782 | 0.739 |
| MaskLabelOnly 或 Hybrid / Coverage | 149 | 0.610 | 0.619 |

## 4. 方法结论

1. **MaskLabelOnly 是必要且很强的简单基线。** 它在空间覆盖和总体人工正确性对齐上与
   Hybrid 相当或更好，说明 SegEarth 不应承担 GT 已经能够直接提供的类别存在性判断。
2. **SegEarth 的有效贡献集中在时相方向。** Temporal 的 AUC 为 0.782、平衡准确率为
   0.739；MaskLabelOnly 无法给出这一维度。因此保留
   “MaskLabelOnly Spatial/Coverage + SegEarth Temporal”的双头 Hybrid 是合理的。
3. **当前不宜把 Hybrid 的各维度强行压成单一 Overall。** Hybrid 的 Overall AUC
   低于 MaskLabelOnly，且偏好排序产生大量自动并列。论文中应分别报告
   Spatial/Coverage 与 Temporal，单一总分只作为补充，并在独立验证集上校准权重和阈值。
4. **Full target 的空间构造应降级为消融对照。** 它引入的分割噪声降低了与人工整体正确性
   的一致性，但仍可用于证明“GT 标签空间证据 + 开放词汇时相证据”的设计选择。

## 5. 后续不依赖服务器即可完成的工作

1. 用新版关键维度表重新标注同一批 50 场景，至少拆分实体、变化方向、位置、数量/属性和
   整体事实性；完成后计算逐维度 Fleiss κ。
2. 对第一版分歧样本做一次三人仲裁，优先处理 GT 漏标题和 Refined 新增细节题。
3. 修复 `test_000217` 的文本版本来源，保证人工表、manifest 和自动结果完全一致。
4. 在本地完成置信区间、阈值敏感性、分实体（building/road）和错误案例汇总；如需新增
   SegEarth 推理或扩展到更多场景，再重新启动 AutoDL。

当前 50 场景结果足以支持论文中的方法选择与先导消融，但不宜单独承担最终统计结论。
正式论文建议增加独立样本、报告置信区间，并以新版逐维度人工标注作为主要效度证据。
