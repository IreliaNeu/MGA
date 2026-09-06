# Grounding DINO Base 与事实评价基线实验归档（2026-08-13）

## 1. 本轮完成内容

在 AutoDL RTX 4090 24 GB 环境中完成了以下非人工实验：

1. 在固定的 LEVIR-MCI 500 个场景、5 组真实模型输出（共 2500 条描述）上，以相同阈值和相同实体查询比较 Grounding DINO Tiny 与 Base。
2. 复现 ALOHa 官方仓库的本地变体，在 5000 条真实输出和 SECOND-CC 200 场景 × 8 种描述的 1600 条受控样本上评价。
3. 按 FMScore 的 yes/no 事实推断协议，以本地 Qwen3-VL-2B 为推理器，对同一组 1600 条受控样本评价。
4. 在同一场景级 bootstrap 协议下比较 ALOHa、FMScore-Qwen 与 MGA-Hybrid。
5. 对 Draft/Refined 的 1000 条 LEVIR-MCI 输出补充 `S*m` 与 `SPIDEr`。
6. 生成一张 Tiny/Base 代表性锚框总览；500 对的逐样本结果只保存在服务器，本地仅保存汇总。

固定 500 场景清单 SHA-256：`87767b8cb3566fc44dc452ab25bcdb4e651b837cb5a56d7ccb7ae98a294bcbb2`。Grounding DINO 两个版本均使用 `box_threshold=0.30`、`text_threshold=0.25` 和 remote-sensing 同义词扩展，未根据测试集调参。

## 2. Grounding DINO Base 对 Tiny

### 2.1 汇总结果

| 指标（5模型宏平均） | Base 相对 Tiny |
|---|---:|
| Coverage | -0.158 |
| Faithfulness | +0.179 |
| Temporal | +0.578 |
| Overall | +0.081 |
| Unverifiable Rate | +0.213 |

| 模型输出 | Tiny Overall | Base Overall | 增量 |
|---|---:|---:|---:|
| Change-Agent | 0.523 | 0.601 | +0.078 |
| Chg2Cap | 0.509 | 0.590 | +0.081 |
| Draft | 0.497 | 0.578 | +0.080 |
| RSICCformer | 0.477 | 0.564 | +0.087 |
| Refined | 0.403 | 0.481 | +0.078 |

Tiny 的平均框掩膜占比为 pre 0.856、post 0.648；Base 降为 pre 0.349、post 0.289。Base 的零框数增加（pre +423、post +233），说明其不是单纯提高召回，而是显著减少大面积、近整图的错误响应，同时更频繁地选择弃权。

这一变化对 MGA 很关键：Tiny 的过大框使两个时相都容易被判定为“存在”，Temporal 宏平均接近 0；Base 将 Temporal 提升约 0.578，并在五种描述输出上稳定提高 Overall。不过 Base 的 Coverage 下降且 Unverifiable Rate 上升，因此应表述为“更准确但更保守”，不能只报告 Overall。

### 2.2 论文位置与必要性

- 若 MGA-OV 是论文的一种正式工作模式，本实验是必要的后端容量/敏感性消融，正文至少保留宏平均表，代表图放正文或附录。
- 它不改变 MGA-Hybrid 作为主方法的定位，也不能证明 Base 已经解决开放词汇定位问题。
- 推荐后续默认采用 Base 作为 Grounding DINO 的 OV 检测后端；Tiny 可作为轻量/低成本对照。
- 代表图中两个选择性定位样本，Tiny 平均掩膜占比为 1.000，Base 分别约为 0.0055 和 0.0137；另一个样本 Base 从 Tiny 的 1.000 改为完全弃权。

说明：中断前曾产生一个未携带 claims 的 Base 试跑目录，所有描述均不可验证。该目录不参与任何统计；有效结果目录名带 `-claims`。

## 3. 已发表事实评价基线

### 3.1 统一受控错误总体区分能力

同一 SECOND-CC 200 场景包含每场景 1 条正确描述和 7 条单因素错误描述，共 1600 条。以下阈值均是事后 oracle threshold，只用于衡量可分性，不应当作部署阈值。

| 方法 | ROC-AUC | 场景 bootstrap 95% CI | Oracle Balanced Acc. |
|---|---:|---:|---:|
| ALOHa local variant | 0.578 | [0.566, 0.590] | 0.660 |
| FMScore-Qwen | 0.823 | [0.812, 0.833] | 0.823 |
| MGA-Hybrid | 0.790 | [0.756, 0.821] | 0.809 |

配对 AUC 差异：

- MGA-Hybrid − ALOHa：+0.211，95% CI [0.174, 0.248]，明确为正。
- MGA-Hybrid − FMScore-Qwen：-0.033，95% CI [-0.070, 0.002]，区间跨 0，不能宣称二者总体区分能力存在显著差异。
- FMScore-Qwen − ALOHa：+0.244，95% CI [0.229, 0.259]。

### 3.2 错误类型揭示的互补关系

ALOHa 的正确描述平均分接近 1。其对实体替换和 no-change 错误敏感，分数分别降到 0.306 和 0.207；但方向反转、额外幻觉和遗漏几乎不降，位置错误仅降到 0.943，关系错误仍为 0.875。原因与方法设计一致：对象名抽取和匹配能够识别名词变化，却不直接验证 A→B 的方向、空间位置、关系或图像证据。

FMScore-Qwen 的正确描述均值为 1.0。它能强烈识别位置和 no-change 错误（均降到 0），方向错误均值 0.5；但额外幻觉为 0.968、关系错误为 0.940，说明只要 GT 事实仍可从句子中推出，增加错误事实并不会得到充分惩罚。它更接近“事实召回/蕴含覆盖”，不是候选描述的视觉事实精度。

MGA-Hybrid 的价值因此不是在一个汇总 AUC 上击败所有文本事实指标，而是补上它们缺少的双时相视觉验证：候选实体是否能在 pre/post 图像中获得证据、变化方向是否一致、位置与关系是否受到证据支持。已有七类配对错误实验中，MGA-Hybrid 对方向、实体、关系和 no-change 的 AUC 为 0.823–0.868；位置和虚构变化仍较弱，AUC 分别为 0.673 和 0.688。这一结果也诚实限定了 MGA 的当前上限。

### 3.3 复现边界

- **ALOHa local variant**：使用官方代码中的 SpaCy 对象解析、MPNet 语义相似度、匈牙利匹配和最小聚合；因大模型下载失败，将仓库默认的 `en_core_web_lg` 换成 `en_core_web_sm 3.7.1`，也没有调用 GPT-3.5。因此不能写作论文默认配置的精确复现。
- **FMScore-Qwen protocol adaptation**：保留论文的事实 yes/no 推断方式，但将原始 Vicuna-13B 换成 Qwen3-VL-2B，采用确定性解码，3200 个问题无解析失败。应将模型替换写进方法名和实验设置。
- **InfoMetIC 未运行**：官方仓库需要约 119 GB 预处理 COCO 特征和约 462 MB 权重，且标准基准训练/评价代码仍标记为待发布。数据盘当时仅余约 6.5 GB；强行改造成双时相指标既不等价，也不经济。论文可以引用和讨论，但不把它列成“已复现”。

## 4. 遥感变化描述常规指标补充

对 1000 条对齐的 LEVIR-MCI Draft/Refined 输出：

| 输出 | S*m | SPIDEr |
|---|---:|---:|
| Draft | 0.713 | 0.762 |
| Refined | 0.588 | 0.609 |

其中 `S*m=(BLEU-4+METEOR+ROUGE-L+CIDEr-D)/4`，`SPIDEr=(SPICE+CIDEr-D)/2`。Draft 在两项参考指标上均高于 Refined；这与语义丰富改写可能偏离参考措辞的现象一致。二者可作为遥感描述社区熟悉的生成质量坐标，但仍完全依赖参考文本，不能评价双时相图像证据。

## 5. 各实验是否必要、是否互补

| 实验 | 优先级 | 论文中的作用 | 与 MGA 的关系 |
|---|---|---|---|
| MGA-Hybrid + 人工评价 | P0，仍待完成 | 证明指标与人类事实判断对齐 | 主结论的最终外部效度证据 |
| FMScore-Qwen | P0 | 最接近遥感变化描述领域的事实匹配基线 | 揭示 GT 事实召回与候选视觉事实精度的差别 |
| ALOHa local variant | P0 | 已发表开放对象幻觉基线 | 说明单图/文本对象匹配缺少时间、空间、关系建模 |
| 标准指标 + S*m | P0 | 与现有 RSICC 文献可比 | 评价参考措辞相似度，不替代 MGA |
| Grounding DINO Base/Tiny | P1（OV 正文或附录） | 后端容量与选择性敏感性 | 解释 MGA-OV 的瓶颈和误差来源 |
| SPIDEr | P2 | 补充参考指标 | 信息与 CIDEr/SPICE 高度重叠，可放附录 |
| InfoMetIC | 当前不运行 | 相关工作与未来对照 | 资源和官方代码状态不足以支撑等价复现 |

这些实验是互补的，不应混成单一排行榜：标准指标衡量参考相似度；ALOHa 衡量对象级幻觉倾向；FMScore 衡量 GT 事实能否被文本蕴含；MGA 衡量候选原子事实能否由双时相视觉/语义证据支持；人工评价检验这些自动分数是否与人的判断一致。

## 6. 对论文主线的影响

本轮实验强化了以下可辩护叙述：

> 传统参考指标回答“生成文本是否像参考文本”，事实匹配指标回答“参考事实是否能从生成文本中推出”，而 MGA 进一步回答“生成文本所声称的实体、方向和关系是否能在双时相图像中找到证据”。

同时必须保留三点限制：

1. MGA-Hybrid 在 pooled AUC 上没有显著超过 FMScore-Qwen；贡献应落在评价维度和错误诊断能力，而非宣称所有总体相关性都最优。
2. Grounding DINO Base 提升精度的代价是 Coverage 下降和 Unverifiable 增加；选择性评价曲线比单点 Overall 更重要。
3. 遗漏错误只有在存在 GT/事实覆盖信息时才可直接判断；纯参考无关的开放视觉证据更擅长验证“说出的事实是否正确”，不能保证“所有重要事实都说全”。

## 7. 仍需完成的人工与低成本工作

1. 完成独立 held-out 人工评价，统一报告 AUC、Balanced Accuracy、Spearman/Kendall、pairwise accuracy、评审一致性与场景级 bootstrap 95% CI。
2. 人工表中分别标注事实正确性、方向、空间/关系、幻觉、遗漏和不可验证，避免只给一个总体主观分。
3. 论文表格将“官方精确复现”“官方本地变体”“协议级模型替换”分列；不能把 ALOHa-local 和 FMScore-Qwen 的数值写成原论文模型数值。
4. 若时间允许，只补一个低成本阈值/coverage 曲线验证 Base 的选择性；不建议为了凑基线下载 119 GB InfoMetIC 资源。

## 8. 产物位置

- 本地汇总：`artifacts/baselines/p0-grounding-factual-2026-08-13/`
- 本地总览图：`grounding-dino-tiny-vs-base-overview.png`
- 服务器完整结果：`/root/autodl-tmp/mga-artifacts/p0-1-unified-baselines-20260813/`
- 服务器代表性逐图可视化：上述目录的 `grounding-visualizations/`
- 本轮来源记录：`sources/fact-evaluation-and-rscc-metric-baselines-2026-08-13.md`

