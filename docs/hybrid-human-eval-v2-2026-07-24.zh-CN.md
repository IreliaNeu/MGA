# Hybrid 与人工评估 v2 说明

日期：2026-07-24

## MaskLabelOnly 的含义

MaskLabelOnly 确实是直接使用 GT 类别 Mask：

- Parser 将 road 映射为 label 1；
- 将 building/house/villa/structure 映射为 label 2；
- 若 Caption 提到的变化类别在对应 GT 类别 Mask 中存在，则实体类别
  Spatial=1；
- Coverage 使用 Caption 提到的类别直接覆盖该类别的 GT 连通分量。

因此它是一个使用参考答案的简单基线，不是独立视觉模型。它只能回答
“Caption 是否提到了 GT 中存在的变化类别”，不能验证：

- Add/Remove/Modify 方向；
- 具体位置；
- 数量与属性；
- GT 本身的漏标；
- GT 类别之外的实体。

MaskLabelOnly 的作用是检验 SegEarth 的空间分割是否提供了超过类别标签查询的
必要增益，不能作为无 GT 场景下的部署指标。

## Hybrid 定义

`hybrid_mask_temporal` 使用：

- Spatial：MaskLabelOnly；
- Coverage：MaskLabelOnly；
- Temporal：SegEarth 的双时相掩膜；
- Context：仍沿用 SegEarth 的实体存在证据；
- No-change：直接检查 GT 变化 Mask。

若 GT 类别存在但 SegEarth 无法提供可靠时相证据：

- Spatial 保留为 1；
- Coverage 保留；
- Temporal=None；
- Claim 状态为 Unverifiable；
- 不计算该 claim 的综合 Faithfulness。

这样不会把“GT 中存在这个类别”错误解释为“Add/Remove/Modify 已被验证”。

## 10 场景小批量结果

输入为人工评估集前10个场景、30条 Caption，复用已有 SegEarth 缓存。

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| Full | Change-Agent | 0.839 | 0.900 | 0.997 | 0.820 | 0.100 |
| Full | Draft | 0.616 | 0.700 | 0.598 | 0.620 | 0.100 |
| Full | Guided | 0.460 | 0.500 | 0.400 | 0.453 | 0.100 |
| MaskLabelOnly | Change-Agent | 1.000 | 0.900 | - | 0.900 | 0.100 |
| MaskLabelOnly | Draft | 0.778 | 0.700 | - | 0.700 | 0.100 |
| MaskLabelOnly | Guided | 0.556 | 0.500 | - | 0.500 | 0.150 |
| Hybrid | Change-Agent | 1.000 | 0.900 | 0.997 | 0.900 | 0.100 |
| Hybrid | Draft | 0.777 | 0.700 | 0.598 | 0.700 | 0.100 |
| Hybrid | Guided | 0.556 | 0.500 | 0.400 | 0.500 | 0.100 |

结果符合预期：

- Hybrid Coverage 与 MaskLabelOnly 一致；
- Hybrid Temporal 与 Full 一致；
- Hybrid 相对 Full 的 Faithfulness 提升来自 GT 类别空间证据，不能解释为
  SegEarth 或 Caption 模型能力提升；
- 10场景仅用于流程验证，不能用于论文结论。

服务器结果：

`/root/autodl-tmp/mga-artifacts/ablations/hybrid-human-10x3-v1`

## 语义丰富改写的建议

MGA 当前并不与语言模板做相似度比较，而是先将描述解析为原子 claim，再验证
实体、变化方向和空间证据。因此句子是否流畅本来就不应影响 MGA。

可以增加“语义保持改写”，但不建议直接让 LLM 自由丰富内容。安全流程应为：

1. 解析原句得到原子 claim 集；
2. 只允许同义替换、句式重排和指代表达展开；
3. 禁止新增实体、方向、位置、数量和属性；
4. 重新解析改写句；
5. 仅当改写前后的规范化 claim 集完全一致时，才接受改写；
6. Original 与 Rewrite 分别评分，用分数差作为 paraphrase robustness。

允许的示例：

`several houses were constructed beside the road`

→ `multiple residential buildings appeared along the roadside`

两者规范化后都应为：

`entity=building, change=add, context=road`

不允许的示例：

`a building appeared`

→ `two large buildings appeared in the lower-right corner`

因为改写新增了数量、属性和位置事实。

论文中更建议称为 `claim-preserving semantic normalization`，而不是
“语义丰富生成”。主结果使用原始 Caption，改写结果作为措辞鲁棒性消融。
