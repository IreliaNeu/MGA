# 实验章节增量更新：P0统一评价基线

> 本文件用于合并进`experiments.zh-CN.v1.md`。所有数值均已完成；人工test相关结论仍保留占位。

## 真实多模型输出与统一协议

为避免评价结论依赖Change-Agent单一输出分布，我们在LEVIR-MCI与LEVIR-CC对齐的1000个测试场景上统一整理Draft、Refined、Change-Agent、RSICCformer和Chg2Cap五类候选，共5000条。每条候选均绑定模型家族、版本、checkpoint或源结果哈希、A/B图像、语义变化掩膜及5条官方参考。所有候选使用相同Parser、阈值、SegEarth-OV-3后端与MGA配置。Refined的无Claim比例为6.5%，高于Draft的1.9%和另外三个模型的0.3%–1.1%，因此我们同时报告Parser Coverage，并不把不可解析文本静默计为事实错误。

在MGA-Hybrid下，Change-Agent、Chg2Cap、RSICCformer、Draft和Refined的Overall分别为0.896、0.892、0.874、0.861和0.736，Temporal分别为0.887、0.882、0.823、0.803和0.696。该结果证明同一Claim—Evidence接口可以处理不同模型家族，但在缺少独立人工正确性标签时只解释为当前评价流水线下的视觉证据支持度，不作为变化描述模型准确率排名。

## 与传统参考指标的关系

按照统一1000场景和每场景5个参考，我们仅对项目的Draft/Refined重新计算参考指标，其余模型的传统结果引用对应论文。Draft与Refined的BLEU-4分别为0.538和0.427，CIDEr为1.216和0.962，SPICE为0.309和0.257，BERTScore-F1为0.961和0.948。所有参考依赖指标均偏向Draft，表明Refined的表达与有限参考存在更大表面或语义偏移；这本身不等价于图像事实错误。

样本级分析表明，BLEU-4、METEOR、CIDEr和BERTScore-F1与MGA Overall的Spearman相关为0.717、0.715、0.714和0.732，但与Temporal仅为0.435、0.350、0.457和0.419。由此可见，MGA Overall与参考指标共享实体和覆盖信号，而Temporal提供了参考相似度不能充分表达的双时相方向信息。

## 单图图文评价对照

我们使用OpenAI CLIP ViT-B/32分别计算描述与A/B图像的相似度，并取均值作为透明的双时相聚合基线。Draft与Refined的均值分别为0.239和0.242，其排序与全部参考指标相反；该基线与MGA Overall、Temporal的Spearman相关分别为-0.400和-0.095。这个结果不是说CLIP缺乏图文语义能力，而是说明简单聚合单图相似度没有显式建模Add/Remove方向，不能直接充当变化事实评价器。

## 可替换视觉后端

为检验MGA是否绑定SegEarth，我们以通用Grounding DINO tiny替换开放视觉后端，在同一固定100场景上使用固定阈值和相同building/road查询。直接把检测框栅格化后，A/B图平均覆盖率分别达到88.0%和67.9%，没有Claim被判为Supported，各模型Overall仅为0.245–0.270；同样本SegEarth-Hybrid为0.817–0.849。该负消融说明MGA接口本身可替换，但粗粒度通用框不足以构造局部双时相证据，遥感像素分割或box-to-mask细化仍是必要的感知组件。

## 错误分层与标注可用性

在SECOND-CC 200场景的七类单因素错误上，MGA-Hybrid对方向、实体、关系和no-change错误的AUC为0.823–0.868，而位置和虚构变化较弱，AUC分别为0.673和0.688。进一步按证据路由分层时，两类均有语义标注、一类标注一类开放、两类均开放的AUC依次为0.924、0.800和0.635。这一连续退化直接支持Hybrid在部分标注条件下的准确性—覆盖折中，同时把开放分割后端确定为主要瓶颈。

我们已固定随机种子，从七类错误各抽取20条、共140条用于人工扰动有效性复核。该复核结果与新的held-out人工事实评价完成后，将补入最终表格并计算场景级bootstrap置信区间。

## 外部效度更新

已完成 ALOHa-local 和 FMScore-Qwen 协议对照，统一结果见 `experiments-factual-baselines-update-2026-08-13.zh-CN.md`。MGA-Hybrid 相对 ALOHa 的 AUC 增益为 0.211，95% CI [0.174, 0.248]；相对 FMScore-Qwen 的差异为 -0.033，95% CI [-0.070, 0.002]，不能宣称总体 AUC 显著更高。该结果支持三类评价信号的互补性，而不是 MGA 对全部事实指标的单调替代。

`[仍待补：独立held-out人工test；报告AUC、Balanced Accuracy、Spearman/Kendall、pairwise accuracy、评审一致性和场景级bootstrap 95% CI。]`
