# MGA 当前进度与 GPT-6 Astra 交接说明（2026-09-06）

> 2026-09-07 续作已归档：[最新验收与后续清单](non-human-work-completion-2026-09-07.zh-CN.md)。本页保留历史背景；4.6 ROI 数字已按权威 JSON 校正。

> 本文件是后续开发与论文写作的权威交接入口。旧的阶段归档、实验增量文档仍用于追溯，但若与本文件冲突，以本文件和对应 `artifacts/**/summary.json` 为准。

## 1. 审计结论

项目应继续推进，但论文主张必须收敛为：**MGA 是面向开放式遥感变化描述的双时相 Claim—Evidence 事实诊断框架，MGA-Hybrid 是主方法，MGA-GT 是理想上界，MGA-OV 是开放视觉后端压力测试。** 当前自动实验已经形成完整方法链和较强受控证据，真正阻塞投稿级结论的是独立人工外部效度，而不是继续增加模型或公式。

当前最可辩护的主线是：

`参考文本相似度无法直接验证图像事实 → 将候选描述拆成原子变化 Claim → 在 T1/T2 中构造实体、方向、位置与关系证据 → 按标注可用性路由 GT/OV 证据并允许 Unverifiable → 用受控错误、标注可用性、真实模型输出和人工判断验证诊断价值`

论文暂定题目：

> **MGA: A Hybrid Evidence-Grounded Evaluation Framework for Open-Ended Remote Sensing Change Descriptions**

可用于引言传播的短题目：

> **Beyond Text Similarity: Evidence-Grounded Evaluation for Remote Sensing Change Descriptions**

## 2. 版本与工作区状态

### 2.1 本地权威工作区

- 路径：`D:\Python_Practice\MGA`
- 分支：`agent/mga-v2-framework`
- 当前恢复提交：`68f63354a25fa8b3bdcd01e12b3fe44f65a46cdd`
- 远端 Draft PR：<https://github.com/IreliaNeu/MGA/pull/1>
- PR 状态：OPEN / Draft；恢复提交的公共推送须以最终恢复记录中的状态为准。
- 本地回归测试：`76 passed`。
- 静态检查：`ruff check src tests` 全部通过。
- CLI：`prepare-feedback / attach-change-agent / validate / parse / perturb / score` 可用。

### 2.2 版本冻结与剩余风险

2026-09-06 已完成版本冻结：248 个代码、测试、配置、论文和紧凑实验归档文件进入提交 `68f6335`，共约 7.37 MiB；私钥、人工原始 XLSX、模型权重、原始数据、逐条 JSONL 和大批逐场景图均被排除。该提交已通过 76 项测试及 `ruff check src tests`，并已恢复到 AutoDL 的独立目录 `/root/autodl-tmp/MGA-current`。因此本地单点丢失风险已显著降低。

仍需注意：

1. 本地仍是论文数值和人工原始表的权威来源；服务器旧目录 `/root/autodl-tmp/MGA` 不能反向覆盖本地。
2. GitHub Draft PR 是否已经包含恢复提交，必须查看本次恢复记录；未完成远端 CI 时不能把旧 CI 解释为最新版验证。
3. 原始数据、权重和逐条输出不进入公开 Git，依靠服务器持久盘、哈希及紧凑汇总恢复。
4. 多数高级功能由 `scripts/` 调用，尚未全部集成到 `mga` CLI；论文复现说明必须给出具体脚本和配置文件。
5. 当前 Ruff 门槛是核心 `src tests`；历史一次性实验脚本尚未完成全仓库格式清理。

## 3. 已实现功能

| 模块 | 当前能力 | 主要位置 | 状态 |
|---|---|---|---|
| 数据规范化 | Draft/Refined、Change-Agent、RSICCformer、Chg2Cap 对齐到统一 manifest | `src/mga/prepare.py`、`scripts/build_unified_caption_eval_manifest.py` | 已实现并用于 5000 条真实输出 |
| Claim 数据结构 | entity/change/location/role/labels/attributes；三态诊断 | `src/mga/models.py` | 已实现 |
| Parser | 启发式、配置化本体、同义词、GLiNER 回退、OpenAI-compatible | `src/mga/parsing/` | 已实现；真实开放语言仍需独立标注验证 |
| 证据模式 | Full target、Temporal delta、GT-ROI、MaskLabelOnly、MGA-GT、MGA-OV、MGA-Hybrid | `src/mga/scoring.py`、`src/mga/evidence_routing_v2.py` | 已实现 |
| 双时相构造 | Add=post−pre、Remove=pre−post、Modify=pre XOR post、source-to-target relation | `src/mga/scoring.py`、`src/mga/semantic_change.py` | 已实现 |
| Grounder | Metadata mask、Grounding DINO、同义查询扩展、SegEarth-OV-3 | `src/mga/grounding/` | 已实现；OV 精度仍是主要瓶颈 |
| Predicted ROI | RGB 特征差分、预测 CD ROI、No-ROI、Oracle GT-ROI | `src/mga/predicted_roi.py` | 已实现并完成校准对照 |
| SECOND 事实图 | 双时相 6 类语义标签构建事实、三类语言样本、受控错误 | `src/mga/semantic_change.py`、相关脚本 | 已实现，200 场景正式实验完成 |
| 错误类型 | direction/entity/hallucination/location/no-change/omission/relation | `scripts/build_minimal_error_taxonomy.py` | 已实现，7×200 错误样本完成 |
| 选择性预测 | risk–coverage、AURC、FSR、supported precision | `scripts/analyze_selective_prediction.py` | 已实现 |
| QA/改写适配 | QA 转 Claim 接口、Claim 等价门控、风格改写分析 | `src/mga/task_adapters.py`、Qwen 脚本 | 接口已实现；自由 QA 实验失败，不能宣称完成任务泛化 |
| 传统/事实基线 | BLEU/METEOR/ROUGE/CIDEr/SPICE/BERTScore、CLIP、ALOHa-local、FMScore-Qwen | `scripts/evaluate_*`、`artifacts/baselines/` | 已实现或协议级适配 |
| 可视化 | MGA 三模式流程图、标注可用性曲线、SegEarth 掩膜、DINO 锚框 | `paper/figures/`、`artifacts/` | 已生成 |

需要注意：项目名称仍叫 Mask-Guided Alignment，但当前方法的核心贡献已经从“一个掩膜重叠分数”发展为“Claim 解析—证据路由—双时相验证—显式弃权”的评价协议。

## 4. 已完成数据与实验

### 4.1 LEVIR-MCI / LEVIR-CC 真实输出

- 统一 1000 场景。
- 每场景 5 条候选：Draft、Refined、Change-Agent、RSICCformer、Chg2Cap，共 5000 条。
- 每场景 5 条官方参考。
- 统一清单 SHA-256：`4a61643fa0dc5325d2f1fa4eb3cecbc53815fca471bac6dd920d3413eb57f275`。
- 5000 条 Claim 清单 SHA-256：`a598d75e07d0e1d12a1940d02c3f802df32d53605f4327bf1cd519f1fe8a537a`。

MGA-Hybrid 汇总：

| 模型 | Faithfulness | Coverage | Temporal | Overall | U |
|---|---:|---:|---:|---:|---:|
| Change-Agent | 0.914 | 0.893 | 0.887 | 0.896 | 0.025 |
| Chg2Cap | 0.906 | 0.876 | 0.882 | 0.892 | 0.016 |
| RSICCformer | 0.885 | 0.872 | 0.823 | 0.874 | 0.015 |
| Draft | 0.884 | 0.867 | 0.803 | 0.861 | 0.037 |
| Refined | 0.798 | 0.744 | 0.696 | 0.736 | 0.083 |

该表只能解释为当前证据流水线下的支持度，**不能在没有独立人工标签时写成生成模型准确率排名**。Refined 的 Parser 无 Claim 率为 6.5%，明显高于 Draft 的 1.9%，其低分部分可能来自 Parser 覆盖问题。

### 4.2 SECOND-CC 200 场景事实图

- 类别：low vegetation、tree、non-vegetated ground、water、playground、building。
- 200 场景、600 个基础评价项。
- 完整 64 个语义类别可用子集已遍历。
- 0%→100% 类别可用性时：Coverage 0.915→1.000，Neutral AUC 0.522→0.944，Balanced Accuracy 0.553→0.935，U 0.085→0。
- 这支持 Hybrid 的“可靠语义证据与开放证据之间的准确性—覆盖折中”，同时也说明纯 OV 条件接近随机，是当前主要瓶颈。

### 4.3 最小错误类型分解

200 场景，每场景 1 条正确描述和 7 条单因素错误，共 1600 条：

| 错误类型 | MGA-Hybrid Neutral AUC | FSR |
|---|---:|---:|
| Direction | 0.868 | 0.000 |
| Entity | 0.823 | 0.000 |
| Hallucination | 0.688 | 0.355 |
| Location | 0.673 | 0.380 |
| No-change | 0.866 | 0.000 |
| Omission* | 0.742 | 0.000 |
| Relation | 0.868 | 0.000 |

`*` Omission 的 0.742 来自 `diagnostic_score = evidence_score × atomic_fact_coverage`。纯 reference-free `evidence_score` 对遗漏近乎失效，因此不能宣称在无事实图/无参考条件下能够检测未表达事实。

按证据路由分层：both-visible / mixed / both-hidden 的 AUC 分别为 0.924 / 0.800 / 0.635，直接定位了开放证据误差。

### 4.4 强事实评价基线

同一 1600 条受控样本：

| 方法 | ROC-AUC | 场景 bootstrap 95% CI | Oracle BAcc |
|---|---:|---:|---:|
| ALOHa-local | 0.578 | [0.566, 0.590] | 0.660 |
| FMScore-Qwen | 0.823 | [0.812, 0.833] | 0.823 |
| MGA-Hybrid | 0.790 | [0.756, 0.821] | 0.809 |

- MGA−ALOHa AUC：+0.211，95% CI [0.174, 0.248]。
- MGA−FMScore-Qwen：−0.033，95% CI [−0.070, 0.002]，差异不显著。
- 不能宣称 MGA 在总体 AUC 上优于全部强基线。
- 可主张的贡献是维度互补：ALOHa 对方向/遗漏/额外幻觉不敏感；FMScore 对仍保留 GT 事实的额外幻觉和关系错误惩罚不足；MGA 显式检查双时相视觉证据。
- ALOHa 使用官方 local variant（SpaCy small + MPNet），FMScore 使用 Qwen3-VL-2B 替代原 Vicuna-13B，必须在论文中写清复现边界。

### 4.5 Grounding DINO Tiny/Base 500 场景消融

固定 500 场景、5 模型、2500 条描述，阈值与查询完全一致。Base 相对 Tiny 的五模型宏平均：Faithfulness +0.179、Temporal +0.578、Overall +0.081，但 Coverage −0.158、U +0.213。

结论：Base 显著减少 Tiny 的近整图框，适合作为 MGA-OV 的默认 Grounding DINO 后端，但更保守。该实验是后端容量/选择性消融，不是主方法创新。

### 4.6 Predicted ROI / No-ROI

在 group-disjoint dev/test 校准中，测试集结果：

| ROI | Coverage | Neutral AUC | BAcc | FSR |
|---|---:|---:|---:|---:|
| No-ROI | 0.968 | 0.748 | 0.746 | 0.309 |
| RGB feature difference | 0.968 | 0.720 | 0.737 | 0.289 |
| Predicted CD ROI | 0.968 | 0.693 | 0.713 | 0.258 |
| Oracle GT-ROI | 0.968 | 0.739 | 0.729 | 0.175 |

结果说明不使用测试 GT 的版本已经实现，但预测 ROI 没有提高总体 AUC；Oracle ROI 主要降低 FSR。论文应将其作为边界/负结果，而不是声称 Predicted-ROI 已解决无 GT 部署。

### 4.7 选择性预测

MGA-Hybrid 在全部可评分样本上的准确率为 0.873、FSR 0.105、AURC 0.095；只保留最高视觉置信度的 19.3% 时，准确率提高到 0.961、FSR 降至 0.041。风险曲线不严格单调，最终阈值必须在独立 development 集固定。

### 4.8 Parser

2026-09-07 补记：下列 0.667/0.770 属于早期基础本体设置。加入既定表面形式配置后，
Ontology F1=1.000、Ontology+GLiNER F1=0.982，见
[配置版汇总](../artifacts/semantic-change/second-cc-200-v1/parser_report_v3.json)。
这衡量已配置表达集的覆盖，不能替代真实开放语言的独立准确率。本次 CPU 重验见
[新汇总](../artifacts/revalidation/2026-09-07/configured-parser-cpu/summary.json)。

- 1200 条受控 Parser 样本。
- Ontology-only：Precision 1.000、Recall 0.500、F1 0.667。
- Ontology + GLiNER：Precision 0.947、Recall 0.650、F1 0.770。
- 表面形式 stress 样本 Exact Match 仍很低，真实描述上的否定、共指、类别歧义和本体外实体尚未得到独立人工标注验证。

### 4.9 人工评价

- 已完成 50 场景 × 3 评审的 pilot。
- 多数票有效率：Change-Agent 0.62、Draft 0.68、Refined/Guided 0.72。
- 人类偏好多数票：Refined 31、Draft 15、Tie 2、NoMajority 2。
- 偏好 Fleiss κ=0.315，属有限一致性。
- 50 场景 pilot 中，Temporal 对人工有效性的 ROC-AUC=0.782、BAcc=0.739；Hybrid Overall AUC=0.512，不能据此证明总分有效。
- `artifacts/ablations/p0-3-minimal-errors-2026-08-12/human_validation_140.csv` 的 140 条扰动有效性字段仍全部为空。
- 尚无独立 held-out、盲化、投稿级人工测试集。

### 4.10 语义改写与 QA

- 50 条改写中 72% 通过精确 canonical Claim 等价门控；被接受样本的 MGA 状态一致率为 1.0，MGA 绝对变化为 0。
- 该实验只能说明“显式确认 Claim 等价之后”的不变性，不能把 28% 语义漂移样本排除后再宣称任意改写鲁棒。
- Qwen 开放 QA 小批量：40 条，Parser success、exact transition、Hybrid coverage 均为 0。该结果为失败实验；目前只能主张 QA 接口可表达，不能主张开放 QA 适应性已验证。

## 5. 论文现状

### 5.1 已有稿件

- 摘要中英双语：`paper/sections/abstract-bilingual-v4.md`
- 引言与相关工作中英双语：`paper/sections/abstract-introduction-related-work.*.v2.md`
- 方法中英双语：`paper/sections/method.zh-CN.v1.md`、`method.en.v1.md`
- 实验中文主稿：`paper/sections/experiments.zh-CN.v1.md`
- 8 月实验增量：`experiments-p0-update-2026-08-12.zh-CN.md`、`experiments-factual-baselines-update-2026-08-13.zh-CN.md`
- 结论与局限中文：`conclusion-limitations.zh-CN.v1.md`
- 图：三模式流程图、标注可用性曲线、DINO Base/Tiny 总览均已生成。

### 5.2 尚未形成的投稿稿件

- 尚未将多个增量文档合并为唯一实验章节。
- 尚无完整英文 Experiments、Conclusion、Limitations。
- 尚无 ACM MM/CVPR 模板中的完整 LaTeX 工程、表格编号、交叉引用和最终参考文献库。
- 摘要 v4 尚未纳入 ALOHa/FMScore 和 Base/Tiny 后续结果；最终摘要还必须等待独立人工 test。
- `experiments.zh-CN.v1.md` 中仍有已被后续实验完成的旧占位，写作时不能机械保留。

## 6. 支持、未验证与被否定的前提

### 已支持

1. 参考指标与双时相事实验证并不等价；Temporal 与文本指标只中等相关。
2. Hybrid 路由在部分标注下形成可测的准确性—覆盖折中。
3. MGA 能对方向、实体、no-change 和关系错误给出比单纯对象匹配更明确的诊断。
4. 更大的开放检测后端能减少粗大框，但会增加弃权。
5. 分量向量比未经校准的单一 Overall 更可靠。

### 尚未验证

1. MGA 各分量在独立 held-out 人工测试上优于强基线。
2. Parser 对真实开放语言的准确率和误差传播。
3. MGA 在更多遥感变化描述数据集上的跨域稳定性。
4. 完全无标注开放场景中的实用性能。

### 已被当前结果否定或需要降级

1. “MGA Overall 已与人工总体判断高度一致”：pilot 不支持。
2. “MGA 在所有强事实指标上最好”：FMScore-Qwen 的总体 AUC 略高，且差异不显著。
3. “Predicted ROI 显著改善无 GT 评价”：当前没有改善 Neutral AUC。
4. “开放 QA 已验证”：Qwen QA 小批量失败。
5. “纯 reference-free MGA 可检测遗漏”：没有事实图时不成立。

## 7. 下一步优先级

### P0：投稿前必须完成

1. **让远端 CI 覆盖冻结提交。** 本地与服务器版本冻结已完成；确认 GitHub Draft PR 包含最终恢复提交并检查 CI。
2. **完成独立人工效度。** 新 held-out 场景，2–3 名评审；按实体正确性、方向、位置/关系、幻觉、遗漏、不可验证分别标注。
3. **填写 140 条扰动有效性表。** 至少验证单因素性、事实错误性和语言自然性。
4. **统一人工相关性统计。** 对传统指标、CLIP、ALOHa-local、FMScore-Qwen、MGA 分量报告 AUC、BAcc、Spearman/Kendall、pairwise accuracy、场景 bootstrap CI 和评审一致性。
5. **合并论文。** 将中文实验主稿和两个增量文档合并，消除过时占位，再生成英文稿。

### P1：强烈建议

1. 建立 100–200 条独立 Claim 标注集，比较 rule-only、GLiNER、LLM fallback 和 Oracle Claim。
2. 给 Grounding DINO Base 做一个低成本 threshold–coverage 曲线；不再扩张大量视觉后端。
3. 在最终人工集上单独验证 Temporal/Spatial/Fact Coverage，而不是只调 Overall 权重。
4. 完成最新相关工作审计，确认截至投稿时的 RSICC/VLM 事实评价论文和 ACM MM 叙述边界。

### P2：不阻塞投稿

- 更强 box-to-mask 或第二个开放分割后端。
- 数量/属性 Claim；仅在事实图可可靠标注时加入。
- WHU-CD 或更大跨数据集实验。
- 开放 QA；必须先修复 QA→Claim Parser，再重新运行。

## 8. 当前服务器状态与接续规则

三端文件级恢复审计及重建顺序见 `docs/server-recovery-audit-2026-09-06.zh-CN.md`。

2026-09-07 已在 43850 实例完成最小必要恢复，并在数据稳定后关机：

- 当前代码入口：`/root/autodl-tmp/MGA-current`；冻结基线 `68f6335`，恢复记录提交位于其后；
- 旧 `/root/autodl-tmp/MGA` 未覆盖，仅作历史追溯；
- MGA 环境：`/root/autodl-tmp/conda-envs/mga`，editable install 指向 `MGA-current`；
- 76 tests、`ruff check src tests`、CLI 与 smoke manifest 均通过；
- SECOND-CC 已恢复为 1,227 对测试影像/语义标签，并重建 200 个事实图、600 条基础样本、1,200 条 Parser 样本和 1,600 条最小错误样本；
- RSICC 与 Chg2Cap 官方代码已恢复，但根据本地已有汇总与哈希，本轮未上传权重、未重跑生成模型；
- 数据盘清理 ZIP 后约剩 21 GiB。

未恢复的是统一五模型和强事实基线的逐样本 JSONL、后期 SegEarth/DINO 缓存与大量逐场景图。其紧凑汇总已经进入 Git；除非新的人工相关性或显著性分析明确需要逐样本输入，否则不要重复大模型实验。

再次启动后首先运行：

```bash
hostname
date
nvidia-smi
df -h / /root/autodl-tmp
git -C /root/autodl-tmp/MGA-current rev-parse --short HEAD
git -C /root/autodl-tmp/MGA-current status --short
ls -ld \
  /root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1 \
  /root/autodl-tmp/mga-artifacts/controlled-errors/second-cc-200-v1 \
  /root/autodl-tmp/caption-bench-20260808 \
  /root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG
```

## 9. GPT-6 Astra 建议起始提示

将下列内容作为切换后的首条工作指令即可：

> 请先完整阅读 `docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md` 和 `docs/server-recovery-audit-2026-09-06.zh-CN.md`。以本地 `D:\Python_Practice\MGA` 为论文数值与人工原始表的权威来源；服务器开发入口是 `/root/autodl-tmp/MGA-current`，不要使用旧 `/root/autodl-tmp/MGA` 覆盖本地。代码冻结与 SECOND-CC 轻量复现输入已恢复，下一步直接完成独立人工效度与论文实验章节合并。论文主线限定为：MGA-Hybrid 通过双时相 Claim—Evidence 验证补充参考文本指标，MGA-GT 是理想上界，MGA-OV 是开放后端压力测试。不得宣称 MGA Overall 已全面优于人工或 FMScore，不得宣称完全无标注、开放 QA 或无参考遗漏检测已经解决。所有结论必须链接到对应汇总 JSON 或人工数据。

## 10. 最可能的审稿问题

1. MaskLabelOnly 已经很强，SegEarth/开放证据究竟提供了什么必要增益？
2. MGA-Hybrid 使用 GT 类别时是否“对着答案评价”，真实无标注部署怎么办？
3. FMScore-Qwen 的总体 AUC 更高，为什么还需要 MGA？
4. Overall 与人工 pilot 对齐很弱，为什么它仍可作为指标？
5. Parser 错误是否主导 Refined 的低分？
6. 受控错误是否真的单因素、自然且具有事实错误？
7. 位置和幻觉 AUC 较低，是否说明视觉证据仍不可靠？
8. Omission 依赖事实图，MGA 到底是 reference-free 指标还是混合评价协议？

回答原则：不回避负结果；将 MGA 定位为分量式事实诊断协议，报告证据来源与 Unverifiable，不把所有冲突压缩成一个未经校准的排行榜分数。

## 11. 关键入口文件

- 方法公式：`docs/mga-three-mode-calculation.zh-CN.md`
- 统一多模型实验：`docs/p0-unified-baselines-and-error-analysis-2026-08-12.zh-CN.md`
- 强事实基线与 DINO Base：`docs/grounding-dino-base-and-factual-baselines-2026-08-13.zh-CN.md`
- SECOND 事实图：`docs/second-cc-200-evidence-experiments-2026-07-26.zh-CN.md`
- 人工 pilot：`docs/three-rater-hybrid-50-analysis-2026-07-24.zh-CN.md`
- Predicted ROI / Selective Prediction：`docs/mga-server-experiments-2026-08-08.zh-CN.md`
- 服务器恢复审计：`docs/server-recovery-audit-2026-09-06.zh-CN.md`
- 最新关机记录：`docs/server-shutdown-record-2026-09-07.zh-CN.md`
- 最新摘要：`paper/sections/abstract-bilingual-v4.md`
- 中文实验主稿：`paper/sections/experiments.zh-CN.v1.md`
- 本地实验汇总：`artifacts/`
- 事实评价来源：`sources/fact-evaluation-and-rscc-metric-baselines-2026-08-13.md`
