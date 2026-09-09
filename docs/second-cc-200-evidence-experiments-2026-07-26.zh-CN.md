# SECOND-CC 200 场景语义证据实验归档

日期：2026-07-26  
目标：验证 MGA 在多类别遥感变化描述评估中的必要性，区分闭集语义标签查找、开放词汇分割、Hybrid 路由和全类别语义 oracle。

## 1. 数据与可复现性

- 数据集：SECOND-CC-AUG。
- 官方代码仓库：<https://github.com/ChangeCapsInRS/SecondCC>
- 数据归档：<https://doi.org/10.5281/zenodo.16937571>
- 压缩包：`SECOND-CC-AUG.zip`
- 文件大小：2,539,187,782 bytes。
- 官方 MD5：`ca930ddb819d68a797938b940d1711f1`
- 本次下载校验：通过。
- 测试集可用双时相语义标签：1,227 对。
- 事实图候选：按文件名排序后的前 600 对测试样本。
- 最终场景数：200。
- 每个场景生成三类文本：事实描述、实体替换矛盾描述、语义等价改写。
- 总评价样本：600 条，各类 200 条。
- 最小变化区域：64 pixels。
- 随机种子：20260726。

SECOND-CC 语义类别及颜色解码如下。

| ID | 类别 | RGB |
|---:|---|---|
| 0 | background | `(255,255,255)` 或 `(0,0,0)` |
| 1 | low vegetation | `(0,255,0)` |
| 2 | tree | `(0,128,0)` |
| 3 | non-vegetated ground | `(128,128,128)` |
| 4 | water | `(0,0,255)` |
| 5 | playground | `(255,0,0)` |
| 6 | building | `(128,0,0)` |

200 个事实图覆盖 20 种语义转移。其中出现较多的转移包括：

- `low vegetation -> non-vegetated ground`：17；
- `building -> non-vegetated ground`：16；
- `building -> tree`：16；
- `non-vegetated ground -> building/low vegetation/tree`：各 16；
- `tree -> building/low vegetation/non-vegetated ground`：各 16。

水体和操场转移较少，因此论文中应同时报告总体结果、类别级结果和长尾限制，避免把该子集表述为完全均衡。

## 2. 事实图与三类评价样本

每个场景首先由双时相语义标签构建事实图。对类别 \(c\)：

- `Add(c) = post(c) AND NOT pre(c)`；
- `Remove(c) = pre(c) AND NOT post(c)`；
- `Modify(c) = pre(c) XOR post(c)`。

本次语义转移样本选择同一位置上占主导的 `source -> target` 转换，并构造：

1. factual：与事实图一致；
2. contradiction：将目标实体替换为场景事实不支持的类别；
3. paraphrase：保持实体与变化关系不变，仅改写表达。

该设计把“事实正确性”与“句子流畅度、模板相似度”解耦，适合验证 MGA 是否真正使用图像证据。

## 3. Parser 实验

### 3.1 初始映射与 GLiNER

初始实验包含 600 条标准文本和 600 条 surface-form 压力文本，共 1,200 条。压力表达包括：

- building：`urban fabric`；
- tree：`wooded parcels`；
- low vegetation：`short green cover`；
- non-vegetated ground：`bare terrain`；
- water：`aquatic zones`；
- playground：`recreation grounds`。

| Parser | Exact Match | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| 基础 ontology | 0.500 | 1.000 | 0.500 | 0.667 |
| 基础 ontology + GLiNER-small | 0.518 | 0.947 | 0.650 | 0.770 |

GLiNER 提升了开放表述召回，但没有可靠解决全部领域释义。

### 3.2 配置化领域词表

新增 `configured_entity_ontology`，将以下内容合并：

1. 数据集类别名；
2. MGA 通用遥感同义词；
3. 数据集版本化 surface-form JSON。

修正后结果：

| Parser | Exact Match | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| 配置化 ontology | **1.000** | **1.000** | **1.000** | **1.000** |
| 配置化 ontology + GLiNER-small | 0.927 | 0.965 | **1.000** | 0.982 |

结论：

- 受控领域类别应以可解释词表为主；
- GLiNER 不应对所有文本无条件运行，否则会引入额外实体、降低精确率；
- 推荐实现“词表先行、仅对未命中片段触发 GLiNER、置信度门控、与类别表冲突时拒绝”的级联 Parser；
- 当前 1.000 是对本次受控 surface-form 集合的覆盖结果，不代表开放自然语言上的泛化上限。论文仍需增加真实模型生成描述和人工改写上的 Parser 分析。

## 4. 四组证据实验定义

| 方法 | 定义 | 作用 |
|---|---|---|
| GTClassLookup | 对每个实体直接检查类别的 add/remove mask 是否非空 | 简单闭集基线 |
| OpenVocabOnly | 全部实体由 SegEarth-OV-3 在 T1/T2 中定位，再构造关系证据 | 纯开放词汇基线 |
| KnownGT-UnknownOV Hybrid | 已知类别使用语义 GT mask；隐藏类别使用 SegEarth；统一计算 source-remove 与 target-add 的空间关系 | MGA 推荐路由 |
| OracleAllClass | 全部类别使用双时相语义 GT 的像素级 `source -> target` 关系 | 可达到的证据上限 |

注意：GTClassLookup 与 Hybrid 的分数定义不同。前者只检查两个原子事件是否分别存在；后者进一步检查 source-remove 和 target-add 是否在真实变化区域中形成一致的空间转换。因此在闭集条件下两者也不要求数值相同。

隐藏类别设为：

- `tree`
- `low vegetation`
- `water`

可见类别为：

- `building`
- `non-vegetated ground`
- `playground`

## 5. 正式结果

### 5.1 闭集条件

| 方法 | Coverage | AUC | Balanced Accuracy | False Support Rate |
|---|---:|---:|---:|---:|
| GTClassLookup | 1.000 | 0.875 | 0.875 | 0.250 |
| OpenVocabOnly | 1.000 | 0.580 | 0.560 | 0.130 |
| Hybrid | 1.000 | **0.944** | **0.935** | **0.070** |
| OracleAllClass | 1.000 | 0.958 | 0.958 | 0.075 |

95% 场景级 bootstrap 区间：

- GTClassLookup AUC：`[0.843, 0.905]`；
- OpenVocabOnly AUC：`[0.538, 0.622]`；
- Hybrid AUC：`[0.911, 0.973]`；
- OracleAllClass AUC：`[0.938, 0.975]`。

Hybrid 相对 OpenVocabOnly：

- AUC 差值：`+0.364 [0.318, 0.413]`；
- Balanced Accuracy 差值：`+0.375 [0.335, 0.415]`。

### 5.2 隐藏类别条件

| 方法 | Coverage | Neutral AUC | Balanced Accuracy | False Support Rate |
|---|---:|---:|---:|---:|
| GTClassLookup | 0.195 | 0.636 | 0.886（仅已评分子集） | 0.229 |
| OpenVocabOnly | 1.000 | 0.580 | 0.560 | 0.130 |
| Hybrid | **1.000** | **0.711** | **0.702** | 0.180 |
| OracleAllClass | 1.000 | 0.958 | 0.958 | 0.075 |

95% 场景级 bootstrap 区间：

- GTClassLookup coverage：`[0.152, 0.237]`；
- GTClassLookup neutral AUC：`[0.602, 0.670]`；
- Hybrid AUC：`[0.672, 0.749]`；
- Hybrid Balanced Accuracy：`[0.663, 0.740]`。

Hybrid 相对 OpenVocabOnly：

- AUC 差值：`+0.131 [0.094, 0.168]`；
- Balanced Accuracy 差值：`+0.142 [0.107, 0.180]`。

区间均不跨 0，说明 Hybrid 的增益在本次 200 场景子集上稳定。

GTClassLookup 的 0.886 Balanced Accuracy 不能与全覆盖方法直接比较，因为它只覆盖 19.5% 样本。用于论文主表时应优先报告 coverage 和 neutral AUC，并把 conditional metric 作为补充。

## 6. SegEarth-OV-3 定位质量

| 类别 | Pre IoU | Post IoU | Add IoU | Remove IoU |
|---|---:|---:|---:|---:|
| building | 0.119 | 0.129 | **0.189** | **0.160** |
| low vegetation | 0.084 | 0.104 | 0.078 | 0.070 |
| non-vegetated ground | 0.070 | 0.082 | 0.047 | 0.053 |
| playground | 0.034 | 0.051 | 0.051 | 0.017 |
| tree | 0.050 | 0.048 | 0.048 | 0.059 |
| water | 0.074 | 0.059 | 0.041 | 0.068 |

可视化观察：

- 建筑在密集城市场景中通常能形成较连续的对象区域，是当前最可靠类别；
- 低植被和非植被地面经常覆盖大面积场景，存在明显过分割；
- 树木与低植被、裸地之间混淆较多；
- 水体在湖泊/河道清晰场景中有效，但小面积或阴影场景不稳定；
- Playground 样本少，且容易与建筑屋顶、硬化地面混淆；
- 纯 OpenVocab 的定位 IoU 较低，解释了其 AUC 接近弱判别水平；
- Hybrid 的意义不是证明 SegEarth 已经足够准确，而是在 GT 类别不完备时保留覆盖能力，并用可靠 GT 约束已知类别。

## 7. 对论文论点的支持

本实验支持以下主张：

1. 仅做 MaskLabelOnly/GTClassLookup 会在类别不完备时出现严重 coverage collapse；
2. 纯开放词汇分割保持覆盖率，但定位噪声导致事实判别性能较低；
3. 按实体路由的 Hybrid 在全覆盖条件下显著优于纯开放词汇方法；
4. 全类别语义 oracle 与 Hybrid 仍有明显差距，说明开放类别定位和时相差分仍是主要瓶颈；
5. Parser 应优先依赖可解释领域映射，轻量模型用于长尾召回，而不是替换规则层。

## 8. 当前限制与后续高优先级实验

1. 200 场景来自测试集前 600 对候选的平衡抽样，不是全测试集随机估计；论文终稿应在完整测试集或多个随机种子上复验。
2. 三类文本为受控生成，适合做机制消融，但不能替代真实变化描述模型输出。
3. 长尾类别不平衡明显；需要类别宏平均、按 source/target 分层 bootstrap。
4. 当前 SegEarth 阈值固定为 confidence/logit 0.10；应在独立验证子集上校准，不能在测试集上调参。
5. 增加面积先验、互斥类别约束、变化 ROI 门控和小区域过滤，重点抑制低植被/裸地过分割。
6. Parser 增加真实生成描述、人工释义、未知实体和否定表达；报告 exact、precision、recall、运行时间和失败类型。
7. 与传统文本指标、CLIP/图文指标、FMScore/ALOHa 类事实指标和人工评价计算 Spearman/Kendall 相关性。
8. 主论文至少报告：
   - 四组路由消融；
   - Full target / Add-Remove / XOR / GT-ROI；
   - 有无同义词；
   - 有无 Parser 模型；
   - 有无 SegEarth；
   - 类别隐藏比例曲线；
   - 置信区间与显著性。

## 9. 本地归档

本地只保存汇总，不保存 600 条逐条得分或 200 张逐场景图：

- `artifacts/semantic-change/second-cc-200-v1/benchmark_manifest.json`
- `artifacts/semantic-change/second-cc-200-v1/parser_report_compact.json`
- `artifacts/semantic-change/second-cc-200-v1/parser_report_v3.json`
- `artifacts/semantic-change/second-cc-200-v1/evidence_summary.json`
- `artifacts/semantic-change/second-cc-200-v1/bootstrap_summary.json`
- `artifacts/semantic-change/second-cc-200-v1/visualization_manifest.json`
- `artifacts/semantic-change/second-cc-200-v1/overview.png`

服务器保留：

- 事实图与三类样本：`/root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1/`
- 四组逐条得分：`.../evidence-v3/`
- 200 个 SegEarth 缓存：`/root/autodl-tmp/mga-cache/segearth-ov3-secondcc-200-v3/`
- 200 张逐场景图：`.../evidence-v3/visualizations/per_scene/`

本地六个已复制文件与服务器 SHA-256 对照一致；Parser v3 随后单独复制。代码测试结果为 `50 passed`。
