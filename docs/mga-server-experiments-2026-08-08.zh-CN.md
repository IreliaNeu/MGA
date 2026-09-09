# MGA服务器续跑实验归档（2026-08-08）

## 1. 完成状态

本轮在AutoDL RTX 4090服务器上完成并保存了以下工作：

- SECOND-CC 200场景、1600条单因素错误样本的三路MGA评分；
- 基于score margin和独立视觉掩膜置信度的Selective Prediction；
- SECOND-CC上的Oracle / Predicted-CD / RGB差分 / No-ROI对照，以及按场景互斥的development/test阈值校准；
- LEVIR-MCI人工评估50场景上的Change-Agent MCI预测ROI与可视化；
- RSICCformer与Chg2Cap官方仓库、LEVIR-MCI 1929对图像索引、1000条MGA交集索引及两套词表的部署准备；
- 2026-08-12补齐两份官方权重，生成各1000条对齐描述，并在固定100场景缓存子集上完成五种MGA证据构造。

RSICCformer和Chg2Cap权重已由用户从官方发布渠道重新上传。两份文件均通过SHA-256固化和ZIP/PyTorch容器全量CRC校验；官方checkpoint、官方仓库提交、词表维度和GPU前向均验证通过。两模型各生成1000条与MGA清单严格对齐的描述，缺失、重复、空文本和清单外样本均为0。

## 2. 最小错误类型分解

每个场景包含1条正确描述及7条单因素错误描述，共1600条。MGA-Hybrid的主要结果如下。

| 错误类型 | Pairwise Acc. | Neutral AUC | Balanced Acc. | FSR | U |
|---|---:|---:|---:|---:|---:|
| 方向颠倒 | 0.735 | 0.868 | 0.860 | 0.000 | 0.000 |
| 错误实体 | 0.735 | 0.823 | 0.860 | 0.000 | 0.000 |
| 虚构变化 | 0.385 | 0.688 | 0.682 | 0.355 | 0.000 |
| 错误位置 | 0.410 | 0.673 | 0.670 | 0.380 | 0.000 |
| No-change误报 | 0.742 | 0.866 | 0.860 | 0.000 | 0.010 |
| 遗漏变化 | 0.730 | 0.742 | 0.860 | 0.000 | 0.000 |
| 错误关系方向 | 0.735 | 0.868 | 0.860 | 0.000 | 0.000 |

结论边界：遗漏检测依赖受控事实图的`atomic_fact_coverage`。移除这一参考信息、只使用reference-free evidence score时，三条路线的遗漏Pairwise Accuracy均为0；MGA-Hybrid的遗漏AUC为0.417、FSR为0.875。因此论文只能主张“验证已表达实体/变化是否有图像证据”；在没有参考事实图时，不能主张检测任意未表达事实。

## 3. Predicted-ROI与阈值校准

SECOND-CC使用97个development场景选阈值、103个互斥test场景报告结果。这里的ChangeFormer使用LEVIR-CD权重，是跨域压力测试。

| ROI | 选择阈值 | Test Neutral AUC | Test BA | Test FSR | Test U |
|---|---:|---:|---:|---:|---:|
| Oracle GT-ROI | 0.310 | 0.739 | 0.729 | 0.175 | 0.032 |
| ChangeFormer Predicted-CD | 0.100 | 0.693 | 0.713 | 0.258 | 0.032 |
| RGB feature difference | 0.189 | 0.720 | 0.737 | 0.289 | 0.032 |
| No-ROI | 0.500 | 0.748 | 0.746 | 0.309 | 0.032 |

Predicted-CD在固定0.5阈值下BA仅0.505，校准后提升到0.713，说明预测ROI输出不能直接当作已校准概率。它未超过No-ROI的AUC/BA，但把FSR从0.309降到0.258，适合作为更保守的部署折中。ChangeFormer在SECOND的ROI IoU只有0.011，结果应视为跨域下界。

在LEVIR-MCI人工评估50场景上，训练域匹配的Change-Agent MCI达到0.509 macro ROI IoU，RGB差分只有0.034；预测变化比例0.050，接近参考0.059。该结果支持Predicted-ROI路线可行，同时显示其强烈依赖领域匹配。

50场景关系评分器只有43/150条描述满足“至少两个Claim”的适用条件，其中人工标签为42正、1负。该子集存在明显选择偏差，不报告caption-level AUC；需要将Predicted-ROI门控扩展到单Claim和no-change后，才能在这150条真实描述上做正式人工效度统计。

## 4. Selective Prediction

在1600条最小错误样本上，MGA-Hybrid近全覆盖时准确率0.873、FSR 0.105、AURC 0.095。按独立视觉掩膜置信度选择：

| 实际覆盖率 | Accuracy | FSR |
|---:|---:|---:|
| 0.193 | 0.961 | 0.041 |
| 0.251 | 0.945 | 0.058 |
| 0.504 | 0.872 | 0.123 |
| 0.753 | 0.883 | 0.106 |

该曲线支持“不确定时拒答”的部署协议，但并非严格单调；置信度阈值必须在独立development集固定。

## 5. 本地归档

- `artifacts/ablations/minimal-error-decomposition-secondcc-200-v1/summary.json`
- `artifacts/ablations/minimal-error-decomposition-secondcc-200-v1/paired_metrics.csv`
- `artifacts/ablations/selective-prediction-minimal-errors-200-v1/`
- `artifacts/ablations/predicted-roi-calibration-secondcc-200-v1/`
- `artifacts/ablations/predicted-roi-human50-mci-v1/summary.json`
- `artifacts/ablations/predicted-roi-human50-mci-v1/roi_overview.png`
- `artifacts/caption-models/prepare_summary.json`
- `artifacts/caption-models/rsiccformer-chg2cap-2026-08-12/`
- `scripts/deploy_or_run_caption_models.py`

本地只保留总览和可复现脚本；逐样本mask、8.9 MB评分JSONL、模型权重和缓存继续保存在AutoDL数据盘。

## 6. 论文写作影响

本轮结果补齐了三个关键证据：错误类型可诊断性、无测试GT时的预测ROI现实折中、以及选择性预测。它们支持MGA-Hybrid作为主方法、MGA-OV作为开放证据下界、MGA-GT作为语义证据上界的叙事。

仍需完成的P0是独立人工test评估和统一强评价基线。RSICCformer/Chg2Cap已补齐真实生成模型多样性：固定100场景pilot表明MGA可以稳定处理两个独立模型家族，但该结果没有人工正确性标签，只能解释为图像证据支持度，不能代替评价指标与人工事实判断的一致性实验。

## 7. RSICCformer / Chg2Cap真实输出补充（2026-08-12）

两份权重及固定官方仓库如下：

| 模型 | 权重大小 | SHA-256 | 官方仓库提交 |
|---|---:|---|---|
| RSICCformer | 1,131,102,595 B | `caf3d36646f1f62f81a58965115fd02fc0222106ef2f299167c1d2fb6bff757d` | `d1505e514c450c3728782ca723e82761e70bafd3` |
| Chg2Cap | 1,317,159,961 B | `d737a92afa3cb76a07f672ee905afb59278211c77ccce517a37ae4637110194c` | `7b8cda937002e614d51a6dab3d949aa7de77c176` |

1000条输出统计：RSICCformer得到239种唯一描述，精确no-change为465条；Chg2Cap得到157种唯一描述，精确no-change为502条。两模型逐场景完全相同描述为488/1000，说明二者既共享LEVIR-CC的模板偏好，也提供了非完全重合的真实输出分布。

在预先固定的100场景building/road缓存子集上，当前Parser审计得到200条描述、0排除。复用SegEarth-OV-3双时相掩膜后，主要结果如下：

| 证据模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---|---:|---:|---:|---:|---:|
| Full target | RSICCformer | 0.547 | 0.833 | 0.877 | 0.669 | 0.378 |
| Full target | Chg2Cap | 0.563 | 0.837 | 0.892 | 0.683 | 0.357 |
| MGA-Hybrid | RSICCformer | 0.858 | 0.825 | 0.877 | 0.838 | 0.015 |
| MGA-Hybrid | Chg2Cap | 0.869 | 0.827 | 0.892 | 0.849 | 0.030 |

这些数值验证了代码链路与多模型适配性，但不构成模型准确率排名。LEVIR-MCI本轮只评价road/building；树和植被等标签外提及不纳入封闭类比较。MaskLabelOnly缺少时相方向验证，因此即使Overall更高也不能解释为评价器更优。完整总览见`artifacts/caption-models/rsiccformer-chg2cap-2026-08-12/`。
