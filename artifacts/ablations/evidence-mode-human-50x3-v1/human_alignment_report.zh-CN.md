# 人工评价与 MGA 证据模式对齐分析

- 场景数：50
- 自动结果匹配的 caption：149/150
- 人工与 LLM-as-Judge 完全一致率：0.480
- Cohen's κ：0.113

## 人工题项概况

| 题项 | 正例 | 比例 |
|---|---:|---:|
| Change-Agent 变化描述成立 | 36 | 0.720 |
| Draft 变化描述成立 | 36 | 0.720 |
| Guided 变化描述成立 | 34 | 0.680 |
| Refined 新增正确细节 | 34 | 0.680 |
| 正确定位但 GT Mask 未标 | 14 | 0.280 |

## 自动指标对人工“变化描述成立”的效度

| 模式 | 指标 | n | Point-biserial r | Spearman ρ | ROC-AUC | Balanced Acc@0.60 |
|---|---|---:|---:|---:|---:|---:|
| full_target | faithfulness | 142 | -0.137 | -0.200 | 0.374 | 0.418 |
| full_target | coverage | 149 | 0.185 | 0.127 | 0.567 | 0.584 |
| full_target | temporal | 93 | 0.351 | 0.284 | 0.785 | 0.728 |
| full_target | overall | 149 | 0.038 | -0.134 | 0.417 | 0.550 |
| full_target | verifiability | 149 | -0.093 | -0.139 | 0.437 | 0.428 |
| temporal_delta | faithfulness | 142 | -0.093 | -0.201 | 0.373 | 0.435 |
| temporal_delta | coverage | 149 | 0.161 | 0.093 | 0.550 | 0.569 |
| temporal_delta | temporal | 93 | 0.351 | 0.284 | 0.785 | 0.728 |
| temporal_delta | overall | 149 | 0.055 | -0.137 | 0.415 | 0.560 |
| temporal_delta | verifiability | 149 | -0.082 | -0.121 | 0.444 | 0.435 |
| gt_roi_gated | faithfulness | 142 | 0.146 | -0.067 | 0.460 | 0.560 |
| gt_roi_gated | coverage | 149 | 0.185 | 0.127 | 0.567 | 0.584 |
| gt_roi_gated | temporal | 93 | 0.351 | 0.284 | 0.785 | 0.728 |
| gt_roi_gated | overall | 149 | 0.177 | -0.055 | 0.466 | 0.603 |
| gt_roi_gated | verifiability | 149 | 0.062 | 0.062 | 0.517 | 0.517 |
| mask_label_only | faithfulness | 142 | 0.167 | 0.145 | 0.569 | 0.560 |
| mask_label_only | coverage | 149 | 0.186 | 0.140 | 0.572 | 0.584 |
| mask_label_only | temporal | 0 | - | - | - | - |
| mask_label_only | overall | 149 | 0.199 | 0.102 | 0.555 | 0.607 |
| mask_label_only | verifiability | 149 | -0.129 | -0.207 | 0.401 | 0.398 |

## 自动指标选择人工偏好描述的能力

| 模式 | 指标 | n | 分摊并列 Top-1 | 自动并列 | 唯一赢家 n | 唯一赢家准确率 |
|---|---|---:|---:|---:|---:|---:|
| full_target | faithfulness | 48 | 0.274 | 42 | 6 | 0.167 |
| full_target | coverage | 49 | 0.306 | 47 | 2 | 0.500 |
| full_target | temporal | 45 | 0.467 | 21 | 24 | 0.542 |
| full_target | overall | 49 | 0.276 | 43 | 6 | 0.167 |
| full_target | verifiability | 49 | 0.354 | 47 | 2 | 0.500 |
| temporal_delta | faithfulness | 48 | 0.274 | 42 | 6 | 0.167 |
| temporal_delta | coverage | 49 | 0.296 | 46 | 3 | 0.333 |
| temporal_delta | temporal | 45 | 0.467 | 21 | 24 | 0.542 |
| temporal_delta | overall | 49 | 0.276 | 43 | 6 | 0.167 |
| temporal_delta | verifiability | 49 | 0.330 | 44 | 5 | 0.200 |
| gt_roi_gated | faithfulness | 48 | 0.264 | 41 | 7 | 0.143 |
| gt_roi_gated | coverage | 49 | 0.306 | 47 | 2 | 0.500 |
| gt_roi_gated | temporal | 45 | 0.467 | 21 | 24 | 0.542 |
| gt_roi_gated | overall | 49 | 0.265 | 42 | 7 | 0.143 |
| gt_roi_gated | verifiability | 49 | 0.337 | 49 | 0 | - |
| mask_label_only | faithfulness | 48 | 0.288 | 44 | 4 | 0.250 |
| mask_label_only | coverage | 49 | 0.306 | 47 | 2 | 0.500 |
| mask_label_only | temporal | 0 | - | 0 | 0 | - |
| mask_label_only | overall | 49 | 0.293 | 45 | 4 | 0.250 |
| mask_label_only | verifiability | 49 | 0.289 | 46 | 3 | 0.000 |

## 使用限制

- 只有1名专家，结果只能作为先导效度分析，不能报告标注者间一致性。
- F/G/H 是场景级二值题，不能区分实体、变化方向、位置、数量与属性错误。
- K 是主观偏好，不等价于事实正确；且题项没有拆分流畅性、信息量与事实性。
- MaskLabelOnly 的 Overall 与含 Temporal 的模式发生了可用权重重归一化，不能只比较 Overall 绝对值。
