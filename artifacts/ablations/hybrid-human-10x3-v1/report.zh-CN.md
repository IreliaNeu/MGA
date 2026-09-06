# MGA 证据构造对照实验

- 场景数：10
- Caption 数：30
- 输入分割缓存：`/root/autodl-tmp/mga-artifacts/segearth-ov3/human-eval-50x3-v1`

## 方法定义

- **full_target**：当前实现：Add 使用 post，Remove 使用 pre，Modify 使用 pre ∪ post。
- **mask_label_only**：不使用 SegEarth；Parser 的 target_labels 直接匹配真实标签 road=1、building=2，不能判断时相方向和静态上下文。
- **hybrid_mask_temporal**：Spatial/Coverage 使用 Parser 直接匹配真实类别标签；Temporal 仅使用 SegEarth 的双时相证据。

## 分模型结果

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| full_target | Change-Agent | 0.839 | 0.900 | 0.997 | 0.820 | 0.100 |
| full_target | Draft | 0.616 | 0.700 | 0.598 | 0.620 | 0.100 |
| full_target | Guided | 0.460 | 0.500 | 0.400 | 0.453 | 0.100 |
| mask_label_only | Change-Agent | 1.000 | 0.900 | - | 0.900 | 0.100 |
| mask_label_only | Draft | 0.778 | 0.700 | - | 0.700 | 0.100 |
| mask_label_only | Guided | 0.556 | 0.500 | - | 0.500 | 0.150 |
| hybrid_mask_temporal | Change-Agent | 1.000 | 0.900 | 0.997 | 0.900 | 0.100 |
| hybrid_mask_temporal | Draft | 0.777 | 0.700 | 0.598 | 0.700 | 0.100 |
| hybrid_mask_temporal | Guided | 0.556 | 0.500 | 0.400 | 0.500 | 0.100 |

## 相对 Full target 的平均变化

| 模式 | 模型 | ΔFaithfulness | ΔCoverage | ΔTemporal | ΔOverall | ΔUnverifiable |
|---|---|---:|---:|---:|---:|---:|
| mask_label_only | Change-Agent | 0.161 | 0.000 | - | 0.080 | 0.000 |
| mask_label_only | Draft | 0.161 | 0.000 | - | 0.080 | 0.000 |
| mask_label_only | Guided | 0.096 | 0.000 | - | 0.047 | 0.050 |
| hybrid_mask_temporal | Change-Agent | 0.161 | 0.000 | 0.000 | 0.080 | 0.000 |
| hybrid_mask_temporal | Draft | 0.161 | 0.000 | 0.000 | 0.080 | 0.000 |
| hybrid_mask_temporal | Guided | 0.096 | 0.000 | 0.000 | 0.047 | 0.000 |

## 解释边界

- MaskLabelOnly 的高分只说明 Caption 提到了真实掩膜中存在的类别；它不验证 add/remove/modify 方向、位置、数量或静态上下文。
- GT-ROI gated 使用真实 ROI 门控，是带有 oracle 信息的乐观对照，不能作为实际部署结果。
- Temporal delta 对 SegEarth 的跨时相配准和掩膜稳定性更敏感；下降既可能来自 Caption 错误，也可能来自分割抖动。
