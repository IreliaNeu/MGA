# MGA 证据构造对照实验

- 场景数：100
- Caption 数：200
- 输入分割缓存：`/root/autodl-tmp/mga-artifacts/segearth-ov3/building-road-100x3-v4`

## 方法定义

- **full_target**：当前实现：Add 使用 post，Remove 使用 pre，Modify 使用 pre ∪ post。
- **temporal_delta**：Add = post - pre，Remove = pre - post，Modify = pre XOR post。
- **gt_roi_gated**：先用对应类别的真实变化 ROI 门控 pre/post，再判断时相存在性；这是乐观的 v1 风格对照。
- **mask_label_only**：不使用 SegEarth；Parser 的 target_labels 直接匹配真实标签 road=1、building=2，不能判断时相方向和静态上下文。
- **hybrid_mask_temporal**：Spatial/Coverage 使用 Parser 直接匹配真实类别标签；Temporal 仅使用 SegEarth 的双时相证据。

## 分模型结果

| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| full_target | Chg2Cap | 0.563 | 0.837 | 0.892 | 0.683 | 0.357 |
| full_target | RSICCformer | 0.547 | 0.833 | 0.877 | 0.669 | 0.378 |
| temporal_delta | Chg2Cap | 0.586 | 0.803 | 0.892 | 0.687 | 0.368 |
| temporal_delta | RSICCformer | 0.561 | 0.800 | 0.877 | 0.668 | 0.375 |
| gt_roi_gated | Chg2Cap | 0.869 | 0.810 | 0.892 | 0.844 | 0.030 |
| gt_roi_gated | RSICCformer | 0.858 | 0.807 | 0.877 | 0.833 | 0.015 |
| mask_label_only | Chg2Cap | 0.895 | 0.827 | - | 0.874 | 0.222 |
| mask_label_only | RSICCformer | 0.890 | 0.825 | - | 0.870 | 0.188 |
| hybrid_mask_temporal | Chg2Cap | 0.869 | 0.827 | 0.892 | 0.849 | 0.030 |
| hybrid_mask_temporal | RSICCformer | 0.858 | 0.825 | 0.877 | 0.838 | 0.015 |

## 相对 Full target 的平均变化

| 模式 | 模型 | ΔFaithfulness | ΔCoverage | ΔTemporal | ΔOverall | ΔUnverifiable |
|---|---|---:|---:|---:|---:|---:|
| temporal_delta | Chg2Cap | 0.023 | -0.035 | 0.000 | 0.004 | 0.012 |
| temporal_delta | RSICCformer | 0.015 | -0.033 | 0.000 | -0.000 | -0.003 |
| gt_roi_gated | Chg2Cap | 0.306 | -0.028 | 0.000 | 0.161 | -0.327 |
| gt_roi_gated | RSICCformer | 0.311 | -0.026 | 0.000 | 0.165 | -0.363 |
| mask_label_only | Chg2Cap | 0.332 | -0.011 | - | 0.190 | -0.135 |
| mask_label_only | RSICCformer | 0.343 | -0.008 | - | 0.201 | -0.190 |
| hybrid_mask_temporal | Chg2Cap | 0.306 | -0.011 | 0.000 | 0.165 | -0.327 |
| hybrid_mask_temporal | RSICCformer | 0.311 | -0.008 | 0.000 | 0.169 | -0.363 |

## 解释边界

- MaskLabelOnly 的高分只说明 Caption 提到了真实掩膜中存在的类别；它不验证 add/remove/modify 方向、位置、数量或静态上下文。
- GT-ROI gated 使用真实 ROI 门控，是带有 oracle 信息的乐观对照，不能作为实际部署结果。
- Temporal delta 对 SegEarth 的跨时相配准和掩膜稳定性更敏感；下降既可能来自 Caption 错误，也可能来自分割抖动。
