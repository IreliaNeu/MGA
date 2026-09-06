# MGA 证据构造对照实验

- 场景数：50
- Caption 数：150
- 输入分割缓存：`/root/autodl-tmp/mga-artifacts/segearth-ov3/human-eval-50x3-v1`

## 方法定义

- **full_target**：当前实现：Add 使用 post，Remove 使用 pre，Modify 使用 pre ∪ post。
- **temporal_delta**：Add = post - pre，Remove = pre - post，Modify = pre XOR post。
- **gt_roi_gated**：先用对应类别的真实变化 ROI 门控 pre/post，再判断时相存在性；这是乐观的 v1 风格对照。
- **mask_label_only**：不使用 SegEarth；Parser 的 target_labels 直接匹配真实标签 road=1、building=2，不能判断时相方向和静态上下文。

## 分模型结果

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| full_target | Change-Agent | 0.700 | 0.863 | 0.872 | 0.767 | 0.130 |
| full_target | Draft | 0.632 | 0.837 | 0.775 | 0.708 | 0.130 |
| full_target | Guided | 0.366 | 0.507 | 0.508 | 0.399 | 0.220 |
| temporal_delta | Change-Agent | 0.737 | 0.853 | 0.872 | 0.784 | 0.180 |
| temporal_delta | Draft | 0.665 | 0.825 | 0.775 | 0.723 | 0.150 |
| temporal_delta | Guided | 0.391 | 0.485 | 0.508 | 0.406 | 0.210 |
| gt_roi_gated | Change-Agent | 0.907 | 0.863 | 0.872 | 0.878 | 0.040 |
| gt_roi_gated | Draft | 0.832 | 0.837 | 0.775 | 0.816 | 0.040 |
| gt_roi_gated | Guided | 0.546 | 0.507 | 0.508 | 0.488 | 0.120 |
| mask_label_only | Change-Agent | 0.918 | 0.865 | - | 0.889 | 0.130 |
| mask_label_only | Draft | 0.847 | 0.839 | - | 0.833 | 0.123 |
| mask_label_only | Guided | 0.567 | 0.509 | - | 0.510 | 0.190 |

## 相对 Full target 的平均变化

| 模式 | 模型 | ΔFaithfulness | ΔCoverage | ΔTemporal | ΔOverall | ΔUnverifiable |
|---|---|---:|---:|---:|---:|---:|
| temporal_delta | Change-Agent | 0.037 | -0.010 | 0.000 | 0.018 | 0.050 |
| temporal_delta | Draft | 0.033 | -0.012 | 0.000 | 0.015 | 0.020 |
| temporal_delta | Guided | 0.025 | -0.022 | 0.000 | 0.007 | -0.010 |
| gt_roi_gated | Change-Agent | 0.207 | 0.000 | 0.000 | 0.112 | -0.090 |
| gt_roi_gated | Draft | 0.200 | 0.000 | 0.000 | 0.108 | -0.090 |
| gt_roi_gated | Guided | 0.180 | 0.000 | 0.000 | 0.089 | -0.100 |
| mask_label_only | Change-Agent | 0.219 | 0.002 | - | 0.122 | 0.000 |
| mask_label_only | Draft | 0.215 | 0.002 | - | 0.125 | -0.007 |
| mask_label_only | Guided | 0.201 | 0.002 | - | 0.111 | -0.030 |

## 解释边界

- MaskLabelOnly 的高分只说明 Caption 提到了真实掩膜中存在的类别；它不验证 add/remove/modify 方向、位置、数量或静态上下文。
- GT-ROI gated 使用真实 ROI 门控，是带有 oracle 信息的乐观对照，不能作为实际部署结果。
- Temporal delta 对 SegEarth 的跨时相配准和掩膜稳定性更敏感；下降既可能来自 Caption 错误，也可能来自分割抖动。
