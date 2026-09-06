# MGA 本地—AutoDL—GitHub 恢复审计（2026-09-06）

## 1. 结论

当前项目没有整体丢失。本地 `D:\Python_Practice\MGA` 保留了最新版方法代码、实验脚本、论文文档、汇总 JSON、总览图和三份人工评价表，应被视为唯一权威工作区。当前 AutoDL 数据盘只保留到约 2026-07-24 的阶段；GitHub Draft PR 也只保存了 7 月早期框架。

真正需要恢复或重建的是：**SECOND-CC 原始数据、RSICCformer/Chg2Cap 的输出与权重、统一 5000 条候选清单、SECOND-CC 逐样本事实图与错误样本、后期事实基线和 Grounding DINO Base 的逐样本结果。** 论文中的主要汇总数字仍在本地，因此不需要从零重新开展全部实验。

在任何服务器恢复操作前，应先冻结并备份本地版本。不要用当前服务器目录覆盖本地。

## 2. 三端版本比较

| 项目 | 本地最新版 | 当前 AutoDL 43850 | GitHub Draft PR |
|---|---:|---:|---:|
| Git HEAD | `7b48834` + 大量未提交工作 | `7b48834` + 7月未提交子集 | `7b48834` |
| 项目源码/脚本/测试/文档清单 | 187 文件 | 53 文件 | 36 文件 |
| 相对本地缺失 | 0 | 134 文件 | 约151文件及所有实验归档 |
| 测试 | 76 passed | 36 passed | 7月 CI，Python 3.10/3.11/3.12 passed |
| `paper/` | 24 文件 | 不存在 | 不存在 |
| 本地汇总 `artifacts/` | 277 文件，约118 MiB | 仓库内不存在；数据盘仅有7月产物 | 不存在 |
| SECOND-CC | 只保留汇总和总览 | 原始数据及后期结果不存在 | 不存在 |
| LEVIR-MCI | 实验汇总存在 | 原始 ZIP、整理后的1000场景存在 | 不保存数据 |
| SegEarth-OV-3 | 代码适配和本地总览存在 | 仓库、环境和 `sam3.pt` 存在 | 不存在 |
| Grounding DINO | Tiny/Base 汇总存在 | 只保留 Tiny 模型缓存 | 不存在 |
| RSICCformer/Chg2Cap | 汇总、哈希和验证信息存在 | 代码、权重、输出均不存在 | 不存在 |

服务器文件名集合不存在本地没有的项目文件。53 个同名文件中，47 个原始字节完全一致；对另外6个规范化换行后，只有 `README.md`、阶段归档和 `test_query_expansion.py` 存在语义版本差异，且本地版本更新、更完整。因此服务器项目目录没有需要反向抢救的代码改动。

GitHub PR：<https://github.com/IreliaNeu/MGA/pull/1>。PR 当前仍为 Draft/Open，仅含 `fb6d694` 与 `7b48834` 两个提交和36个文件，不能作为8月最新版的备份。

## 3. 已安全保留，不需要重跑的内容

### 3.1 本地方法与写作资产

- 最新 MGA-GT / MGA-OV / MGA-Hybrid、Parser、Predicted-ROI、SECOND fact graph、QA adapter 等代码；
- 120 个脚本、47 个测试、8 个配置文件；
- 摘要、引言/相关工作、方法、实验增量、结论与流程图；
- 三份人工评价表和新版人工评价模板；
- SECOND、七类错误、强事实基线、DINO Tiny/Base、五模型统一评价的汇总 JSON；
- SegEarth 批量总览、SECOND 总览、Predicted-ROI 总览和 DINO 对比总览。

### 3.2 当前服务器仍可复用的内容

- `/root/autodl-tmp/datasets/LEVIR-MCI-dataset.zip`，约2.6 GiB；
- `/root/autodl-tmp/datasets/organized`，约308 MiB；
- `/root/autodl-tmp/datasets/MGA_segearth.jsonl` 与 `change_agent.zip`；
- `/root/autodl-tmp/third_party/SegEarth-OV-3`，约3.3 GiB；
- SegEarth 环境及 `weights/sam3/sam3.pt`；
- MGA Python 3.11.15 环境、SegEarth Python 3.12.13 环境；
- Grounding DINO Tiny 模型缓存；
- 7月的 SegEarth 掩膜、Grounding 框和人工 pilot 逐样本结果。

这些内容不应删除，但也不能替代8月后期实验。

## 4. 必须恢复或重建的内容

### P0-A：先保护本地最新版

这是最高优先级，因为当前最新代码尚未进入 GitHub：

1. 审计 `.tmp/`、`tmp/`、缓存与大图，更新 `.gitignore`；
2. 将 `src/`、`scripts/`、`tests/`、`configs/`、`docs/`、`paper/`、`requirements/` 和 `sources/` 纳入版本控制；
3. 将小型实验汇总 JSON/CSV 和人工表格做独立压缩备份；人工原始表可不进入公开仓库；
4. 提交后运行76项测试和 Ruff，再推送 Draft PR；
5. 为不适合 Git 的数据、权重和逐样本结果生成 `SHA256SUMS` 并保存到独立存储。

在完成这一步之前，不建议直接把本地目录覆盖到服务器。

### P0-B：恢复 SECOND-CC 与可重现实验输入

当前本地、服务器和 GitHub 都没有 SECOND-CC 原始影像与双时相语义标签，需要重新下载或从原持久盘恢复：

```text
/root/autodl-tmp/datasets/SECOND-CC/SECOND-CC-AUG.zip
/root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG
```

恢复数据后，使用本地已有脚本、固定 `seed=20260726`、`min_pixels=64` 重建：

```text
fact_graphs.jsonl
evaluation_samples.jsonl
parser_all_samples.jsonl
minimal_error_manifest.jsonl
minimal-error scores.jsonl
predicted-ROI open_vocab_scores.jsonl
predicted-ROI hybrid_scores.jsonl
```

本地保存的 `benchmark_manifest.json`、各类 `summary.json` 和 `overview.png` 可作为重建验收基准。基础协议应恢复为200场景、600条三类样本；七类错误协议应为200条事实描述加7×200条单因素错误，共1600条。

### P0-C：优先找回两个模型的输出 JSONL

比权重更值得优先抢救的是两个体积不足1 MiB的生成结果：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `rsiccformer_mga1000.jsonl` | 568150 | `79dc9157d2b798a6c5f97e6641d4760ff6e628539a34b04d9e2b7379f4da16ca` |
| `chg2cap_mga1000.jsonl` | 547296 | `d344c99636cdc54152df8ae9c5c1c95192f5fb25814366238477a02fa642f018` |
| `caption_models_mga1000_raw.jsonl` | 2000行 | `17d707cc299c93118c3f9c4e79227b8fe5253804f5a16fde81aa3cf3e2f77ba9` |
| `caption_models_cached100_claims.jsonl` | 426467 | `6300cedd0c0691c8e87c916d94571381a0e1200a7f75c31d21387a0079ccd164` |

先检查上传电脑、AutoDL 文件存储、网盘或旧实例是否还有这些文件。如果能找回输出，就不必为了评价论文重新部署两个生成模型。

如果输出确实无法找回，再恢复权重并重跑：

| 模型 | 权重字节数 | SHA-256 |
|---|---:|---|
| RSICCformer | 1131102595 | `caf3d36646f1f62f81a58965115fd02fc0222106ef2f299167c1d2fb6bff757d` |
| Chg2Cap | 1317159961 | `d737a92afa3cb76a07f672ee905afb59278211c77ccce517a37ae4637110194c` |

对应仓库提交分别为 RSICCformer `d1505e514c450c3728782ca723e82761e70bafd3`、Chg2Cap `7b8cda937002e614d51a6dab3d949aa7de77c176`。

### P0-D：重建统一候选与逐样本评价文件

当前只保留了统计汇总，没有以下原始评价输入：

- 1000场景×5模型的 `model_outputs_manifest.jsonl`；
- 对应5000条 Claim 清单；
- ALOHa-local 与 FMScore-Qwen 的逐样本输出；
- 传统指标与 MGA 的逐样本联合表；
- DINO Tiny/Base 500场景、2500条描述的逐样本框与分数。

这些文件是后续计算人工相关性、bootstrap、错误案例和论文复核所必需的。恢复顺序应为：模型输出 → 统一 manifest → Claim → MGA/传统指标/事实基线。现有本地汇总可验证最终均值，但不能替代逐样本显著性分析。

## 5. 按需恢复，而非立即恢复

以下内容可从公开源重新下载，或只在确实重跑相应实验时恢复：

- Grounding DINO Base 权重与缓存；
- Qwen3-VL-2B 权重，用于 FMScore 适配、改写和失败的 QA 小批量；
- RSICCformer、Chg2Cap 仓库和大体积权重——如果已找回输出 JSONL，可暂不恢复；
- ALOHa/FMScore 第三方依赖；
- 每场景 DINO/SegEarth 可视化图。

## 6. 无需恢复的内容

- `pip-cache`、`conda-pkgs` 和可重新创建的包缓存；
- 已有 Conda 环境的完整复制；
- 所有历史中间 checkpoint；
- 大量逐场景可视化。用户已明确本地只保留总览图，投稿只需选定少量代表案例；
- 失败的开放 QA 全量扩展；除非后续将 QA 提升为论文主张；
- 重复的旧 SegEarth 100×3 实验。当前服务器仍有旧逐样本结果，本地也有汇总与总览。

## 7. 推荐恢复顺序

1. **本地冻结与双份备份。** 这是防止剩余成果继续丢失的首要动作。
2. **在服务器新建最新版工作目录。** 建议同步到 `/root/autodl-tmp/MGA-current`，验收后再决定是否替换旧目录。
3. **恢复 SECOND-CC。** 先验证图像、A/B语义标签数量和压缩包校验值。
4. **寻找两个约0.5 MiB的模型输出 JSONL。** 找不到才上传约2.3 GiB权重并重跑。
5. **重建统一 manifest、Claim 和 SECOND 逐样本文件。** 用现有 summary 与哈希验收。
6. **只重跑投稿必需的 P0 逐样本评价。** 包括人工相关性所需的传统指标、ALOHa-local、FMScore-Qwen、MGA分量和最小错误分解。
7. **按需下载 DINO Base/Qwen。** 不提前占用磁盘。

## 8. 当前风险判断

- **论文文字与主要汇总结论：低风险。** 本地保存完整。
- **最新代码：中高风险。** 只存在本地未提交工作区，必须立即冻结。
- **完全复现实验：高风险。** 关键逐样本输入和原始 SECOND 数据已不在三端，需要恢复或确定性重建。
- **模型生成输出：高风险但恢复成本可控。** 两个关键 JSONL 很小；若找不到，可用已记录的仓库提交和权重哈希重跑。
- **人工实验：低风险。** 三份已填表格在本地；独立 held-out 人工测试尚未完成，本来就需要新建。

