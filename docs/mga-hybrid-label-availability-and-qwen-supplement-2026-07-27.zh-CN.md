# MGA-Hybrid 标注可用性曲线与 Qwen3-VL 补充实验归档

日期：2026-07-27  
主方法：MGA-Hybrid  
数据集：SECOND-CC、LEVIR-MCI  
小模型：Qwen3-VL-2B-Instruct  
原则：本地仅保存汇总、论文图和复现实验代码，逐条 Qwen 输出与 64 个子集明细保留在服务器数据盘。

## 1. 结论摘要

本轮结果支持将 MGA-Hybrid 确立为论文主方法，并把“标注可用性曲线”作为最高优先级主实验。

1. 在 SECOND-CC 的 200 个场景、600 条受控样本上，随着可用语义类别由 0% 增加到 100%，Hybrid 的 Neutral AUC 从 0.522 提升到 0.944，Balanced Accuracy 从 0.553 提升到 0.935。
2. 严格可验证性协议下，Coverage 从 0.915 提升到 1.000，Unverifiable Rate 从 0.085 下降到 0。
3. False Support Rate 并非全程单调：在只提供 1–2 个类别时由 0.156 上升到约 0.188，随后随标签增多下降到 0.070。这说明不完整 GT 与 OV 证据混合时仍需校准，不能只强调平均 AUC 的提升。
4. 0.05 与 0.10 的 OV 置信度门槛产生完全相同的曲线；0.20 增加了低标注阶段的弃权，但不改变全 GT 端点。
5. Qwen3-VL 的 40 场景自由问答未能得到可用的端到端准确性结果：模型频繁输出 SECOND-CC 本体外的 `industrial/commercial/urbanized area`，Parser 覆盖与精确转移准确率均为 0。该结果应作为小模型识别失败案例，不能写成 MGA 已在真实开放 QA 输出上验证成功。
6. 在同一 40 场景构造的 120 条受控 QA 回答上，Q+A 适配器不修改 MGA 评分器即可得到 Hybrid Neutral AUC 0.918、Balanced Accuracy 0.925 和 False Support Rate 0.125，说明任务接口具有可迁移性。
7. 强风格改写的 40 条样本中，30 条通过严格 Claim 等价门控；对这些样本，MGA 状态一致率为 1.000、平均绝对分数差为 0，而 BLEU-4 和 ROUGE-L 相对同一人工参考分别下降约 20.4% 和 21.3%。

因此，主论文应以标注可用性曲线、四路证据对照和人工效度为核心；QA 与风格改写只作为补充实验，不承担主要有效性结论。

## 2. 标注可用性曲线

### 2.1 实验设置

- 数据集：SECOND-CC。
- 场景数：200。
- 文本数：600，包括 factual、paraphrase 和 contradiction 各 200 条。
- 类别数：6：
  - building；
  - low vegetation；
  - non-vegetated ground；
  - playground；
  - tree；
  - water。
- 可用类别子集：枚举六类的完整幂集，共 \(2^6=64\) 个子集。
- 横轴：可直接使用语义 GT 的类别比例 \(k/6\)。
- 对不在可用子集中的实体，Hybrid 回退到既有 SegEarth-OV-3 双时相缓存。
- 每个比例报告所有同规模类别子集的均值，并用最小值—最大值表示类别组成差异。

严格可验证性协议规定：

- OV source 实体必须在 T1 具有非空掩膜且置信度不低于 0.10；
- OV target 实体必须在 T2 具有非空掩膜且置信度不低于 0.10；
- 若必要时相证据缺失，则记为 Unverifiable；
- 若实体证据有效但 source-remove 与 target-add 未形成关系，则记为数值 0，即明确不支持。

### 2.2 五项主指标

| 可用类别 | 子集数 | Coverage | Neutral AUC | Balanced Accuracy | False Support Rate | Unverifiable Rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0/6（0%） | 1 | 0.915 | 0.522 | 0.553 | 0.156 | 0.085 |
| 1/6（16.7%） | 6 | 0.929 | 0.590 | 0.595 | 0.181 | 0.071 |
| 2/6（33.3%） | 15 | 0.943 | 0.658 | 0.647 | 0.188 | 0.057 |
| 3/6（50%） | 20 | 0.957 | 0.727 | 0.707 | 0.179 | 0.043 |
| 4/6（66.7%） | 15 | 0.971 | 0.797 | 0.776 | 0.155 | 0.029 |
| 5/6（83.3%） | 6 | 0.986 | 0.869 | 0.852 | 0.119 | 0.014 |
| 6/6（100%） | 1 | 1.000 | 0.944 | 0.935 | 0.070 | 0.000 |

类别组成影响较大。例如在 50% 标注条件下：

- Neutral AUC 范围为 0.656–0.833；
- Balanced Accuracy 范围为 0.608–0.824；
- False Support Rate 范围为 0.109–0.241；
- Coverage 范围为 0.920–0.995。

因此，论文不能只写“标注比例越高性能越好”，还应强调“哪些类别被标注”同样重要。后续若增加一张补充图，优先做每个类别的边际收益或 Shapley-style contribution，而不是继续增加随机样本数。

### 2.3 结果解释

Neutral AUC 和 Balanced Accuracy 随可用类别增加而稳定提升，说明 Hybrid 能把可靠 GT 证据逐步转化为更强的事实判别能力。Coverage 同时增加、Unverifiable Rate 下降，说明开放词汇回退确实缓解了纯 GT lookup 的 coverage collapse。

False Support Rate 在低标注阶段先升后降。可能原因是：当 source 和 target 中只有一端使用准确 GT、另一端仍使用噪声较大的 OV 掩膜时，混合关系的局部膨胀与真实变化 ROI 可能形成偶然重叠。该现象不会否定 Hybrid，但要求论文明确提出：

1. Hybrid 不是任意少量标注都无条件优于纯 OV；
2. 低标注阶段需要类别选择策略、置信度校准或关系级一致性约束；
3. 主张应聚焦整体判别能力和覆盖—准确性折中，而不是宣称所有指标严格单调。

### 2.4 置信度敏感性

| OV 门槛 | 0% Coverage | 0% Unverifiable | 0% Neutral AUC | 50% Coverage | 50% Neutral AUC | 100% AUC |
|---:|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.915 | 0.085 | 0.522 | 0.957 | 0.727 | 0.944 |
| 0.10 | 0.915 | 0.085 | 0.522 | 0.957 | 0.727 | 0.944 |
| 0.20 | 0.853 | 0.147 | 0.504 | 0.925 | 0.728 | 0.944 |

0.05 与 0.10 完全一致，说明当前掩膜存在性约束比低置信度门槛更具决定性。0.20 主要增加弃权，并未在 50% 标注处带来 AUC 增益。当前推荐保留 0.10，与既有 SegEarth 推理门槛一致；正式论文应声明该阈值并非在测试集上调优。

## 3. QA 适应性小实验

### 3.1 真实 Qwen3-VL 回答

- 场景：SECOND-CC 40 个平衡选取场景。
- 输入：T1/T2 两幅 256×256 RGB 影像。
- 问题：开放询问主要地表转移，要求回答旧类别、新类别和大致位置。
- 模型：Qwen3-VL-2B-Instruct，greedy decoding。

结果：

- Parser 成功率：0；
- 精确 source-to-target 准确率：0；
- Hybrid 可评分覆盖：0。

主要失败不是 Q+A 适配器，而是 2B 模型输出了标签体系外或视觉上错误的概念。例如，它将地表变化描述为 `industrial area -> residential area`、`agricultural land -> commercial area`，而 SECOND-CC 的事实类别并不包含这些概念。若强行把这些词映射到 building 或 non-vegetated ground，会把模型幻觉变成人为“正确”，因此本轮没有扩大同义词表。

论文可将该结果作为失败案例，说明开放 QA 评价必须同时面对生成模型本体漂移和 Parser 长尾表达问题。不能据此宣称 MGA 已完成真实开放 QA 的端到端验证。

### 3.2 受控 QA 接口验证

对同一 40 个场景，根据事实图为每个问题构造：

1. factual answer；
2. claim-preserving paraphrase；
3. target-entity contradiction。

共 120 条回答，全部通过同一个 Q+A 适配器进入原 MGA 验证器。

| 证据方法 | Coverage | Neutral AUC | Balanced Accuracy | False Support Rate |
|---|---:|---:|---:|---:|
| GTClassLookup | 1.000 | 0.813 | 0.813 | 0.375 |
| MGA-Hybrid | 1.000 | **0.918** | **0.925** | **0.125** |
| OracleAllClass | 1.000 | 0.913 | 0.913 | 0.175 |

该实验支持的结论是：只增加输入适配器，MGA 可以处理 QA 形式的声明；它不证明当前 Qwen3-VL-2B 能正确完成遥感开放问答。

## 4. 语义丰富与强风格改写

### 4.1 普通丰富改写

- 来源：LEVIR-MCI 的 Draft 25 条、Change-Agent 25 条。
- 所有样本至少包含一个 Changed Claim。
- 通过 Claim 等价门控：36/50（0.72）。
  - Draft：15/25（0.60）；
  - Change-Agent：21/25（0.84）。
- 通过门控的样本：
  - MGA 状态一致率：1.000；
  - 平均绝对 MGA 差：0。

普通改写相对温和，其 BLEU/ROUGE 下降幅度不足以作为主要语言不变性证据。

### 4.2 强风格压力改写

- 原始描述：Draft 10 条、Change-Agent 10 条。
- 风格：technical nominalized、active narrative。
- 总改写：40 条。
- 通过 Claim 等价门控：30/40（0.75）。
- 通过者的 MGA 状态一致率：1.000；
- 通过者的平均绝对 MGA 差：0。

| 指标 | 原始描述对人工参考 | 风格改写对同一参考 | 相对变化 |
|---|---:|---:|---:|
| BLEU-1 | 0.327 | 0.273 | -16.8% |
| BLEU-4 | 0.188 | 0.150 | -20.4% |
| ROUGE-L | 0.325 | 0.256 | -21.3% |
| Token F1 | 0.328 | 0.267 | -18.6% |
| MGA status agreement | 1.000 | 1.000 | 0 |
| MGA mean absolute delta | 0 | 0 | 0 |

这里的 BLEU 为加一平滑句级 BLEU，ROUGE-L 和 Token F1 由可复现本地实现计算。正式投稿版本仍应补充官方实现的 corpus BLEU、METEOR、CIDEr 和 BERTScore；本轮结果可作为机制性补充，不替代完整传统指标表。

严格门控非常重要：10/40 改写改变了可解析 Claim，不能用其证明 MGA 应当“不变”。正确表述是：对经 Claim 等价确认的事实保持改写，MGA 复用相同图像证据并保持评分不变；发生 semantic drift 的改写应作为错误样本单独分析。

## 5. 论文写作建议

### 主文

1. 主方法：MGA-Hybrid。
2. 主实验：
   - 四路证据对照；
   - 标注可用性曲线；
   - 三评审人工效度；
   - Parser 与视觉后端误差传播。
3. 标注曲线主表报告：
   - Coverage；
   - Neutral AUC；
   - Balanced Accuracy；
   - False Support Rate；
   - Unverifiable Rate。
4. 主图使用 `fig_label_availability_curve.pdf`。

### 补充材料

1. 0.05/0.10/0.20 阈值敏感性；
2. 64 个类别子集的 min–max 范围；
3. 120 条受控 QA 适配实验；
4. 40 条强风格改写；
5. Qwen3-VL-2B 自由回答失败案例。

### 不应使用的表述

- “MGA 已在真实开放 QA 上取得良好结果”；
- “所有 Hybrid 指标随标注比例严格单调提升”；
- “MGA 完全不依赖标注”；
- “Qwen 改写天然保持事实”；
- “Unverifiable=0 说明所有视觉证据可靠”。

## 6. 本地文件

- 严格曲线汇总：`artifacts/semantic-change/second-cc-200-v1/label-availability-curve-v2-verifiable/curve_summary.json`
- 阈值 0.05：`artifacts/semantic-change/second-cc-200-v1/label-availability-th005/curve_summary.json`
- 阈值 0.20：`artifacts/semantic-change/second-cc-200-v1/label-availability-th020/curve_summary.json`
- 论文曲线 PDF：`paper/figures/fig_label_availability_curve.pdf`
- 论文曲线 PNG：`paper/figures/fig_label_availability_curve.png`
- Qwen 基础汇总：`artifacts/qwen3-vl-supplement-v1/summary.json`
- 受控 QA 汇总：`artifacts/qwen3-vl-supplement-v1/controlled_qa_summary.json`
- 强风格改写汇总：`artifacts/qwen3-vl-supplement-v1/style-stress-20x2/summary.json`
- 中文方法：`paper/sections/method.zh-CN.v1.md`
- 英文方法：`paper/sections/method.en.v1.md`

## 7. 服务器归档

- Qwen 模型：`/root/autodl-tmp/models/Qwen3-VL-2B-Instruct`
- Qwen 实验：`/root/autodl-tmp/mga-artifacts/qwen3-vl-supplement-v1`
- 标注曲线：
  - `.../second-cc-200-v1/label-availability-curve-v1`
  - `.../second-cc-200-v1/label-availability-curve-v2-verifiable`
  - `.../second-cc-200-v1/label-availability-th005`
  - `.../second-cc-200-v1/label-availability-th020`

服务器逐条结果不复制到本地，符合“本地只保存总览”的归档要求。
