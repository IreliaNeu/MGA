# ACM MM后续清单补充（2026-08-12）

本文件对`mga-acmmm-next-work-checklist-2026-07-27.zh-CN.md`中P0-1和P0-3的状态作增量更新；完整结果见`p0-unified-baselines-and-error-analysis-2026-08-12.zh-CN.md`。

## 已完成

- [x] 统一1000场景、5模型、5000候选的`sample_id/model_family/model_variant/caption/provenance`清单。
- [x] 对5000候选使用同一Parser并运行5种MGA证据模式。
- [x] Draft/Refined补齐BLEU-1/4、METEOR、ROUGE-L、CIDEr、SPICE和BERTScore；RSICCformer/Chg2Cap传统指标按用户要求引用原论文。
- [x] 增加OpenAI ViT-B/32双时相CLIP均值对照。
- [x] 增加内部Reference-Claim-F1控制，并明确它不是已发表强事实评价基线。
- [x] 报告Draft/Refined样本级相关性与成对排序。
- [x] 完成Grounding DINO替换视觉后端消融及同样本SegEarth对照。
- [x] P0-3七类单因素错误各200条及分类型AUC、Balanced Accuracy、Pairwise Accuracy、FSR、U。
- [x] 补充按Hybrid路由、实体、位置、变化面积分层。
- [x] 生成七类各20条、共140条的人工有效性核验表。
- [x] 完成 ALOHa 官方 local variant 与 FMScore-Qwen 协议适配，并与 MGA-Hybrid 做场景级 bootstrap 对照。
- [x] 完成 Grounding DINO Tiny/Base 固定500场景消融和代表性锚框总览。
- [x] 补充遥感变化描述 `S*m` 与 SPIDEr 复合指标。

## 仍需用户参与

- [ ] 完成held-out、盲化、独立人工test，建议2–3名评审。
- [ ] 填写`human_validation_140.csv`三项：是否单因素、是否事实错误、是否自然。
- [ ] 核对RSICCformer/Chg2Cap论文中待引用传统指标的具体backbone、split与表格行。
- [x] ALOHa 采用无需 API 的 SpaCy-small + MPNet 官方本地接口；论文必须标为 local variant。

## 仍需非人工工作

- [x] 已完成 ALOHa-local 与 FMScore-Qwen；InfoMetIC 因 119 GB 官方特征要求和不完整基准代码不再作为投稿阻塞项。
- [ ] 人工test完成后，统一计算所有指标对人工维度的AUC、Balanced Accuracy、Spearman/Kendall、pairwise accuracy和场景级bootstrap 95% CI。
- [ ] 建立独立Parser标注集，优先修复Refined 6.5%的无Claim问题，避免用下游结果反向调Parser。
- [ ] 可选为Grounding DINO加入box-to-mask细化；当前通用框结果已足够作为负消融。
- [ ] 仅在事实图具有可靠计数/属性原子后增加数量/属性错误。
