# MGA 证据构造对照实验

- 场景数：100
- Caption 数：300
- 输入分割缓存：`/root/autodl-tmp/mga-artifacts/segearth-ov3/building-road-100x3-v4`

## 方法定义

- **full_target**：当前实现：Add 使用 post，Remove 使用 pre，Modify 使用 pre ∪ post。
- **temporal_delta**：Add = post - pre，Remove = pre - post，Modify = pre XOR post。
- **gt_roi_gated**：先用对应类别的真实变化 ROI 门控 pre/post，再判断时相存在性；这是乐观的 v1 风格对照。
- **mask_label_only**：不使用 SegEarth；Parser 的 target_labels 直接匹配真实标签 road=1、building=2，不能判断时相方向和静态上下文。

## 分模型结果

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| full_target | Change-Agent | 0.548 | 0.804 | 0.884 | 0.657 | 0.375 |
| full_target | Draft | 0.561 | 0.856 | 0.859 | 0.681 | 0.392 |
| full_target | Guided | 0.562 | 0.848 | 0.847 | 0.673 | 0.418 |
| temporal_delta | Change-Agent | 0.567 | 0.779 | 0.884 | 0.661 | 0.355 |
| temporal_delta | Draft | 0.581 | 0.820 | 0.859 | 0.682 | 0.387 |
| temporal_delta | Guided | 0.576 | 0.805 | 0.847 | 0.669 | 0.398 |
| gt_roi_gated | Change-Agent | 0.846 | 0.776 | 0.884 | 0.812 | 0.045 |
| gt_roi_gated | Draft | 0.870 | 0.834 | 0.859 | 0.843 | 0.030 |
| gt_roi_gated | Guided | 0.868 | 0.825 | 0.847 | 0.832 | 0.040 |
| mask_label_only | Change-Agent | 0.874 | 0.794 | - | 0.843 | 0.193 |
| mask_label_only | Draft | 0.899 | 0.846 | - | 0.876 | 0.172 |
| mask_label_only | Guided | 0.904 | 0.842 | - | 0.878 | 0.157 |

## 相对 Full target 的平均变化

| 模式 | 模型 | ΔFaithfulness | ΔCoverage | ΔTemporal | ΔOverall | ΔUnverifiable |
|---|---|---:|---:|---:|---:|---:|
| temporal_delta | Change-Agent | 0.019 | -0.025 | 0.000 | 0.004 | -0.020 |
| temporal_delta | Draft | 0.019 | -0.037 | 0.000 | 0.001 | -0.005 |
| temporal_delta | Guided | 0.014 | -0.043 | 0.000 | -0.003 | -0.020 |
| gt_roi_gated | Change-Agent | 0.298 | -0.028 | 0.000 | 0.155 | -0.330 |
| gt_roi_gated | Draft | 0.308 | -0.023 | 0.000 | 0.162 | -0.362 |
| gt_roi_gated | Guided | 0.306 | -0.023 | 0.000 | 0.159 | -0.378 |
| mask_label_only | Change-Agent | 0.325 | -0.010 | - | 0.186 | -0.182 |
| mask_label_only | Draft | 0.338 | -0.011 | - | 0.195 | -0.220 |
| mask_label_only | Guided | 0.341 | -0.006 | - | 0.206 | -0.262 |

## 解释边界

- MaskLabelOnly 的高分只说明 Caption 提到了真实掩膜中存在的类别；它不验证 add/remove/modify 方向、位置、数量或静态上下文。
- GT-ROI gated 使用真实 ROI 门控，是带有 oracle 信息的乐观对照，不能作为实际部署结果。
- Temporal delta 对 SegEarth 的跨时相配准和掩膜稳定性更敏感；下降既可能来自 Caption 错误，也可能来自分割抖动。
