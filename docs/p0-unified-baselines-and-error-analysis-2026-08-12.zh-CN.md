# P0-1统一评价基线与P0-3错误分析归档（2026-08-12）

## 1. 本轮结论

本轮完成了不依赖新增人工标注的主要计算环节：统一五模型输出清单、Draft/Refined传统与语义文本指标、双时相CLIP聚合对照、5000条全量MGA评分、Grounding DINO视觉后端替换消融、最小错误类型分层、选择性预测复核，以及10%扰动人工有效性核验表。

结论应严格写为：MGA能够把候选描述中的实体与变化关系转化为可定位、可诊断的双时相图像证据；它与文本匹配指标有共享信号，但Temporal分量提供了文本指标和单图CLIP聚合不能替代的方向证据。当前结果尚不能替代独立人工事实判断，也不能把MGA均分解释成Change Caption模型准确率。

## 2. 统一候选清单

统一清单包含LEVIR-MCI/LEVIR-CC对齐测试子集1000个场景、每场景5条候选，共5000条：

| 模型 | 数量 | 说明 |
|---|---:|---|
| Draft | 1000 | 项目原始Draft |
| Refined | 1000 | 源字段为`Guided`，归档中显式保留原字段 |
| Change-Agent | 1000 | 同一模型家族的最终输出 |
| RSICCformer | 1000 | 官方checkpoint真实推理输出 |
| Chg2Cap | 1000 | 官方checkpoint真实推理输出 |

每个场景包含5条官方参考描述。统一清单SHA-256为`4a61643fa0dc5325d2f1fa4eb3cecbc53815fca471bac6dd920d3413eb57f275`；5000条Claim清单SHA-256为`a598d75e07d0e1d12a1940d02c3f802df32d53605f4327bf1cd519f1fe8a537a`。

Parser无Claim比例为：Chg2Cap 0.3%、RSICCformer 0.3%、Change-Agent 1.1%、Draft 1.9%、Refined 6.5%。因此Refined分数下降的一部分可能来自开放表达未被当前规则Parser覆盖，论文必须同时报告Parser Coverage，不能全部解释为图像事实错误。

## 3. Draft/Refined统一文本指标

传统指标只对本项目需要比较的Draft/Refined重新计算；RSICCformer与Chg2Cap的传统指标采用各自论文原始报告值，不与本表混写。本表使用同一1000场景、每条5个参考。

| 模型 | BLEU-1 | BLEU-4 | METEOR | ROUGE-L | CIDEr | SPICE | BERTScore-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Draft | 0.8161 | 0.5378 | 0.3739 | 0.7254 | 1.2161 | 0.3085 | 0.9612 |
| Refined | 0.7272 | 0.4270 | 0.3256 | 0.6381 | 0.9620 | 0.2568 | 0.9480 |

实现与配置：BLEU/METEOR/ROUGE/CIDEr使用RSICC官方评价代码；SPICE使用`pycocoevalcap 1.2`的官方Java实现；BERTScore使用`bert-score 0.3.13`、`roberta-large`第17层、多参考、无IDF、不做baseline rescale。

所有参考依赖指标都更偏向Draft。这只能说明Draft更接近有限参考表达，不能单独证明Draft更符合图像事实。BERTScore差距小于BLEU/CIDEr，说明语义嵌入缓解但没有消除参考表达偏差。

## 4. 图文与内部事实对照

OpenAI CLIP ViT-B/32分别计算描述与A、B图像的余弦相似度，并报告两者均值。这是透明的单图指标聚合，不显式编码Add/Remove方向。

| 模型 | CLIP-A | CLIP-B | BiTemporal-CLIP Mean |
|---|---:|---:|---:|
| Draft | 0.2355 | 0.2423 | 0.2389 |
| Refined | 0.2392 | 0.2458 | 0.2425 |

CLIP聚合略偏向Refined，而参考文本指标均偏向Draft，说明非时相基线的排序并不稳定。样本级BiTemporal-CLIP Mean与MGA Overall的Spearman相关为-0.400，与MGA Temporal仅为-0.095。

另提供内部`Reference-Claim-F1`控制：Draft 0.8837、Refined 0.7993。它使用同一Parser解析候选和参考并取五参考最大F1，依赖参考文本且没有图像证据，不作为已发表事实评价基线，也不能替代ALOHa/InfoMetIC等外部方法。

## 5. 五模型全量MGA结果

SegEarth-OV-3对每个场景的A/B图像各分割一次building和road，复用于5个模型与5种证据模式；本轮不保存逐场景掩膜。共1000场景、5000候选，耗时1035秒，峰值GPU显存5409 MiB。

主方法MGA-Hybrid结果：

| 模型 | Faithfulness | Coverage | Temporal | Overall | U |
|---|---:|---:|---:|---:|---:|
| Change-Agent | 0.9140 | 0.8933 | 0.8874 | 0.8963 | 0.0247 |
| Chg2Cap | 0.9058 | 0.8757 | 0.8820 | 0.8916 | 0.0162 |
| RSICCformer | 0.8846 | 0.8720 | 0.8233 | 0.8744 | 0.0152 |
| Draft | 0.8842 | 0.8673 | 0.8028 | 0.8611 | 0.0368 |
| Refined | 0.7984 | 0.7443 | 0.6962 | 0.7365 | 0.0828 |

该表证明同一Claim—Evidence接口能够处理多个独立模型家族，但不是模型准确率排名。Refined的Parser无Claim率更高；没有独立人工事实标签前，不能将其较低MGA均分直接写成Refined更差。

MaskLabelOnly的Overall普遍更高，但Temporal为空，说明它是标签范围内很强的空间/类别查找基线，不验证变化方向；主文不能用Overall的绝对大小宣称它优于或劣于Hybrid。

## 6. 样本级相关性与成对排序

在Draft/Refined共2000条样本上，BLEU-4、METEOR、CIDEr、BERTScore-F1与MGA Overall的Spearman相关分别为0.717、0.715、0.714和0.732；与MGA Temporal分别仅为0.435、0.350、0.457和0.419。这表明MGA Overall仍含有实体/覆盖等与参考指标共享的信号，而Temporal提供相对独立的双时相方向维度。

Draft与Refined同场景成对排序中：

| 指标 | Draft胜 | Refined胜 | 平局 | Refined-Draft均值 |
|---|---:|---:|---:|---:|
| BLEU-4 | 285 | 90 | 625 | -0.1259 |
| CIDEr | 286 | 93 | 621 | -0.2541 |
| SPICE | 257 | 77 | 666 | -0.0517 |
| BERTScore-F1 | 300 | 140 | 560 | -0.0132 |
| BiTemporal-CLIP Mean | 152 | 242 | 606 | +0.0036 |
| MGA Overall | 171 | 52 | 777 | -0.1247 |

平局多的主要原因是大量no-change模板或两阶段文本完全一致。该分析是指标间关系，不是人工效度；投稿主结论仍依赖独立人工test。

## 7. Grounding DINO替换后端消融

采用通用领域`IDEA-Research/grounding-dino-tiny`，固定box threshold=0.30、text threshold=0.25，使用遥感同义查询扩展，并把检测框栅格化为MGA掩膜。在与SegEarth严格相同的100场景、5模型上：

- Grounding DINO没有产生Supported Claim；541条Contradicted、244条Unverifiable；
- 预测框平均覆盖A图88.0%、B图67.9%；
- 各模型Overall约0.245–0.270；
- 同样本SegEarth-Hybrid各模型Overall约0.817–0.849。

该负结果说明MGA框架可替换视觉后端，但通用大框检测不能直接提供细粒度时相证据。论文应将其写成后端消融与失败分析，支持遥感像素级分割或“检测框+分割细化”的必要性，而不是宣称Grounding DINO本身无效。

## 8. P0-3错误分层与选择性预测

已有SECOND-CC 200场景、每场景1条正确描述和7种单因素错误，共1600条。Hybrid的方向、实体、关系、no-change AUC为0.823–0.868；位置和虚构变化较弱，AUC分别0.673和0.688，FSR分别0.380和0.355。

新增分层结果：

| Hybrid证据路由 | AUC | Balanced Acc. | Pairwise Acc. |
|---|---:|---:|---:|
| 两类均有语义标注 | 0.924 | 0.925 | 0.857 |
| 一类标注、一类开放 | 0.800 | 0.815 | 0.657 |
| 两类均走开放证据 | 0.635 | 0.666 | 0.362 |

这个梯度直接量化了Hybrid随标注可用性变化的准确性—覆盖折中。按位置分层时center最弱，AUC 0.687；按实体分层时tree/water较弱，与既有SegEarth误差分析一致。

选择性预测复核：MGA-Hybrid全可评分集准确率0.873、FSR 0.105、AURC 0.095；保留最高视觉置信度的19.3%时，准确率0.961、FSR 0.041。风险曲线不严格单调，阈值仍必须在development集固定。

`human_validation_140.csv`包含七类错误各20条、共140条，占1400条错误样本的10%。需要人工填写是否单因素有效、是否确为事实错误、是否流畅。遗漏检测依赖受控事实图的atomic fact coverage；纯reference-free evidence不能检测未表达事实。数量/属性错误暂未构造，因为当前事实图和Claim Schema没有独立可验证的计数或属性原子。

## 9. 仍需用户参与的实验

1. 完成独立、盲化、held-out人工test评估；建议至少2–3名评审，不与现有50场景pilot混合调参。
2. 填写`human_validation_140.csv`中的三项人工有效性核验；如果人力有限，可先各类10条，再补到20条。
3. 确认论文中RSICCformer/Chg2Cap传统指标引用的具体表格与模型配置，避免把论文中的不同backbone/split数值误填到统一表。
4. 若使用需要账户/API的ALOHa，确认允许的LLM与检测器配置；推荐把它作为单图事实评价对照，并显式说明它不验证双时相方向。

## 10. 后续非人工优先级

- P0：复现一个已发表强事实评价基线。优先ALOHa，因为它与MGA同样强调实体级幻觉、可定位性和开放类别；但应分别对A/B图像运行或做透明聚合，并把不能验证Add/Remove方向作为实验对象。
- P0：待独立人工test完成后，统一报告各指标的AUC、Balanced Accuracy、Spearman/Kendall、pairwise accuracy与场景级bootstrap 95% CI。
- P1：改进Refined开放表达的Parser召回，并在独立标注的Claim解析集上评测，不能只凭下游MGA分数调Parser。
- P1：Grounding DINO增加box-to-mask细化或换用遥感开放检测器；当前通用框基线保留为负消融即可。
- P2：若事实图可可靠提供实例数或属性，再扩展数量/属性错误；当前不阻塞主论文。

