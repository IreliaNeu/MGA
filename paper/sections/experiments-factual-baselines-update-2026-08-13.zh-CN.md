# 实验章节增补：事实评价基线与开放定位后端

## 已发表事实评价基线

为区分“参考事实覆盖”与“双时相视觉证据一致性”，我们在 SECOND-CC 200 个场景构造的 1600 条受控描述上比较 MGA-Hybrid 与两类已发表事实评价思路。每个场景包含一条正确描述和方向、实体、幻觉、位置、无变化、遗漏、关系七类单因素错误描述。ALOHa-local 使用官方代码的 SpaCy 对象解析、MPNet 相似度、匈牙利匹配和最小聚合；FMScore-Qwen 保留 FMScore 的 yes/no 事实推断协议，但将原文 Vicuna-13B 替换为本地 Qwen3-VL-2B。所有置信区间均以场景为重采样单位、执行 2000 次 bootstrap。

| Method | ROC-AUC | 95% CI | Oracle BAcc |
|---|---:|---:|---:|
| ALOHa-local | 0.578 | [0.566, 0.590] | 0.660 |
| FMScore-Qwen | 0.823 | [0.812, 0.833] | 0.823 |
| MGA-Hybrid | 0.790 | [0.756, 0.821] | 0.809 |

MGA-Hybrid 相对 ALOHa 的配对 AUC 增益为 0.211，95% CI 为 [0.174, 0.248]；相对 FMScore-Qwen 的差异为 -0.033，95% CI 为 [-0.070, 0.002]，不能据此宣称总体 AUC 显著更高。更关键的差异出现在错误类型上：ALOHa 对方向反转、额外幻觉和遗漏几乎不响应，对位置与关系错误也仅有弱响应；FMScore-Qwen 能检查参考事实是否仍被文本蕴含，但额外幻觉和关系错误的平均得分仍分别达到 0.968 和 0.940。相比之下，MGA 直接验证候选文本提出的实体、时相存在性、方向和空间关系，因此与两类文本事实指标形成互补，而不是对其进行同构替代。

## Grounding DINO 模型尺寸消融

我们进一步在固定的 LEVIR-MCI 500 个场景和五组真实系统输出上比较 Grounding DINO Tiny 与 Base。两者使用相同的原子 claims、遥感同义词扩展及预注册阈值（box 0.30，text 0.25），共评价 2500 条描述。相对 Tiny，Base 的五模型宏平均 Faithfulness、Temporal 和 Overall 分别提高 0.179、0.578 和 0.081，但 Coverage 下降 0.158，Unverifiable Rate 上升 0.213。Tiny 的 pre/post 平均框占比分别为 0.856/0.648，Base 降至 0.349/0.289，表明 Base 显著抑制了近整图误定位，但采用了更保守的证据策略。

该结果说明开放词汇后端容量会实质影响 MGA-OV 的校准与选择性，因而我们在后续实验中默认使用 Base，并同时报告 Coverage 与 Unverifiable Rate。该消融不改变 MGA-Hybrid 的主方法定位：语义标签可用时优先使用高精度语义证据，标签缺失的类别再交由开放词汇后端验证。

## 遥感变化描述常规复合指标

在 1000 个对齐 LEVIR-MCI 场景上，Draft/Refined 的 `S*m` 分别为 0.713/0.588，`SPIDEr` 分别为 0.762/0.609。这些参考驱动的复合指标显示 Draft 更贴近参考措辞，但不包含双时相视觉验证。我们因此将其作为生成质量与既有 RSICC 文献的可比坐标，而不把它们视为 MGA 的替代指标。

## 人工评价占位

`[待补：独立 held-out 人工评价；报告 AUC、Balanced Accuracy、Spearman/Kendall、pairwise accuracy、评审一致性和场景级 bootstrap 95% CI，并按方向、幻觉、遗漏、空间/关系和不可验证分层。]`

