# MGA 本地—AutoDL—GitHub 恢复审计（2026-09-06）

## 1. 结论

本轮恢复已经完成“保证框架完整性与论文可接续”的目标：本地最新版形成冻结提交 `68f6335`，服务器在不覆盖旧目录的前提下建立 `/root/autodl-tmp/MGA-current`，恢复 SECOND-CC 原始解压数据并确定性重建事实图、Parser 输入和最小错误清单，同时补回 RSICC/Chg2Cap 官方代码。76 项测试、核心 Ruff、CLI 和 smoke manifest 均通过。

根据用户决定，本轮没有重复下载两个变化描述模型的权重，也没有重跑 RSICCformer、Chg2Cap、SegEarth、ALOHa、FMScore 或 Grounding DINO Base。对应论文汇总、验证信息和原始输出哈希已进入 Git 冻结提交，足以继续论文写作；需要逐样本统计时再从备份恢复 JSONL，而不是默认重跑大模型。

以下第 2–8 节保留**恢复前审计与决策依据**，最终服务器状态和校验值以第 9 节为准。任何时候都不要用历史服务器目录覆盖本地权威工作区。

## 2. 恢复前三端版本比较

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

## 4. 恢复前判定的必须恢复或重建内容

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

## 9. 恢复执行记录（2026-09-07）

### 9.1 代码冻结与服务器工作区

- `.gitignore` 已排除缓存、临时下载、人工原始 XLSX、模型权重、原始数据、逐条 JSONL 和大批逐场景图；小型 JSON/CSV/Markdown 汇总进入版本控制。
- 冻结提交：`68f63354a25fa8b3bdcd01e12b3fe44f65a46cdd`，248 个文件，约 7.37 MiB。
- 传输 bundle：`/root/autodl-tmp/mga-recovery/mga-68f6335.bundle`；SHA-256 为 `bf28c117b51ac87157bac51f4f4465611d423b9199c8cd342084cd24704ab3ed`。
- 新工作区：`/root/autodl-tmp/MGA-current`；旧 `/root/autodl-tmp/MGA` 未覆盖、未删除。
- `/root/autodl-tmp/conda-envs/mga` 的 editable install 已指向新工作区。
- 本地与服务器均为 76 tests passed；`ruff check src tests` 通过；CLI 和一条 smoke manifest 验证通过。
- `ruff check .` 会在历史一次性实验脚本中报告格式问题，不能误写为全仓库 Ruff clean。

GitHub 是公开目的地。恢复提交的公共推送只在用户确认精确仓库、分支和排除项后执行；最终是否已推送应结合本任务交付信息和 PR #1 的 HEAD 核验，不能仅看旧 CI。

### 9.2 SECOND-CC 数据恢复

- 来源：官方 `SECOND-CC-AUG.zip`；
- 字节数：`2539187782`；
- MD5：`ca930ddb819d68a797938b940d1711f1`；
- SHA-256：`2c6743084aa588bd9004b96aac3debe32382f2ce7993ade0f25de11b5414dd83`；
- 本地下载完成后校验通过；上传服务器后再次校验，ZIP 全量完整性测试无错误；
- 解压目录：`/root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG`，约 4.3 GiB；
- `test/rgb/A`、`rgb/B`、`sem/A`、`sem/B` 各 1,227 张 PNG；
- 前 600 对 RGB 语义标签已解码到 `/root/autodl-tmp/datasets/SECOND-CC/decoded-ids`；
- 本地临时 ZIP、分段文件和下载脚本已删除；服务器上传 ZIP 在解压验收后删除。

恢复后数据盘占用约 30/50 GiB，剩余约 21 GiB。

### 9.3 确定性重建结果

使用 `candidate_limit=600`、`limit=200`、`min_pixels=64`、`seed=20260726` 重建：

| 文件 | 行数 | SHA-256 |
|---|---:|---|
| `semantic-eval/second-cc-200-v1/manifest.json` | — | `36ed910f1eff3506b02077fb8122a9f4682d2cd95c1c20cab7c2f9d58acd43c5` |
| `semantic-eval/second-cc-200-v1/fact_graphs.jsonl` | 200 | `6698c00a81f2bef7b6e248f476b406653f39e8c78e0d1f3897e9deae22f38a42` |
| `semantic-eval/second-cc-200-v1/evaluation_samples.jsonl` | 600 | `22c7eeb25e943f6c06d594acb0bd2752809371d31d0e30c6504b6ef4c420cfe9` |
| `semantic-eval/second-cc-200-v1/parser_all_samples.jsonl` | 1200 | `7e3fc5925a307802bd45bb0a74b217d951613f6386e022069e695506a099104a` |
| `controlled-errors/second-cc-200-v1/minimal_error_manifest.jsonl` | 1600 | `cde0a928ca7c8c522c82b7f5a07b3f9a7bc4e4a7b4a135488af5c4b8ba0d7d87` |

benchmark manifest 与本地历史归档逐字节一致；20 种语义转移计数、三类样本各 200、拒绝候选 67 均与历史实验一致。最小错误清单满足 200 条原始事实加 7×200 条单因素错误，`strict_single_factor=true`。

### 9.4 Caption 模型代码与取舍

- Chg2Cap 官方代码：`/root/autodl-tmp/caption-bench-20260808/repos/Chg2Cap`，提交 `7b8cda937002e614d51a6dab3d949aa7de77c176`；
- RSICC 官方代码：`/root/autodl-tmp/caption-bench-20260808/repos/RSICC`，提交 `d1505e514c450c3728782ca723e82761e70bafd3`；
- 已建立 `incoming/`、`outputs/`、`mga-eval/`，总占用约 162 MiB；
- 未上传权重、未重跑生成，避免约 2.3 GiB 权重及重复推理成本。

### 9.5 关机条件

关机前必须再次确认：新工作区与恢复文档同步、76 项测试和核心 Ruff 通过、SECOND-CC 四目录各 1,227 张、重建文件行数与哈希存在、ZIP 已清理、数据盘仍有余量。满足这些条件后执行 `sync` 和 `shutdown -h now`。再次启动时以 `docs/autodl-current-state-2026-09-06.zh-CN.md` 为入口。
