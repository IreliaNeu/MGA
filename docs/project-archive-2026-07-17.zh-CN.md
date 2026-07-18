# MGA 项目阶段归档（2026-07-17）

## 1. 归档目的

本文记录 MGA 项目当前代码状态、已经实现的功能、尚未完成或尚未经过真实环境验证的部分，以及后续在 AutoDL 上继续开发时的优先任务和验收标准。

本文面向后续开发者、实验复现者和论文撰写者。判断某项能力是否“已经完成”时，以当前仓库代码和自动化测试为准，不以路线图或接口占位为准。

## 2. 当前版本快照

| 项目 | 当前状态 |
| --- | --- |
| 仓库 | `https://github.com/IreliaNeu/MGA` |
| 开发分支 | `agent/mga-v2-framework` |
| 基线提交 | `fb6d694 build MGA v2 evaluation framework` |
| Draft PR | `https://github.com/IreliaNeu/MGA/pull/1` |
| Python | 3.10 及以上 |
| 本地单元测试 | 9 项通过 |
| GitHub CI | Python 3.10、3.11、3.12 全部通过 |
| 项目阶段 | 可运行的研究框架；尚未完成真实 GPU 数据验证和正式实验 |

当前代码尚未合并到 `main`。在 Draft PR 合并前，AutoDL 必须显式检出开发分支：

```bash
git clone --branch agent/mga-v2-framework \
  https://github.com/IreliaNeu/MGA.git
cd MGA
git checkout fb6d694
```

## 3. 项目目标与当前评价对象

项目用于评价遥感双时相变化描述是否得到以下证据支持：

- 前时相图像 `pre_image`；
- 后时相图像 `post_image`；
- 像素级变化掩码 `change_mask`；
- 从自然语言描述中抽取的原子声明 `claims`；
- Grounding DINO 或预计算实体掩码提供的视觉定位证据。

当前主要比较对象为：

- `Draft`：原始描述；
- `Guided`：结合 teacher feedback 后的修正描述；
- `Change-Agent`：每个样本对应一个文本文件的模型输出。

`Win_caption`、`reason_draft` 和可选的 `judge_model` 属于 LLM-as-Judge 元数据，分别保存为：

```text
metadata.llm_judge_winner
metadata.llm_judge_reason
metadata.llm_judge_model
```

它们不属于人工评价。五人独立人工评价尚未接入，后续必须使用单独的数据表、导入模块和统计流程。

## 4. 已实现功能

### 4.1 统一数据模型与清单校验

已经定义稳定的数据结构：

- `SampleRecord`：一个模型在一个双时相样本上的描述；
- `AtomicClaim`：从描述中拆出的可验证原子声明；
- `GroundingEvidence`：实体在前、后时相上的支持掩码与置信度；
- `ClaimScore`、`CaptionScore`：声明级和描述级 MGA v2 结果；
- `LegacyCaptionScore`：MGA v1 重建结果。

清单读取器已经实现：

- JSONL 逐行解析和行号错误定位；
- 必填字段校验；
- 相对路径按清单目录解析；
- `(sample_id, model)` 重复检查；
- 图像和掩码文件存在性检查。

关键文件：`src/mga/models.py`、`src/mga/io.py`、`docs/data-format.md`。

### 4.2 现有实验结果转换

`mga prepare-feedback` 已实现：

- 将一条 feedback JSONL 记录展开成对齐的 `Draft` 和 `Guided` 两条记录；
- 保存 ground-truth caption、teacher feedback、feedback 状态和 LLM-as-Judge 元数据；
- 支持使用 `{id}`、`{sample_id}`、`{image_stem}` 构造变化掩码文件名；
- 不把 LLM-as-Judge 标签混入人工评价。

`mga attach-change-agent` 已实现：

- 按 `sample_id` 或源图像文件名匹配 Change-Agent 的 `.txt` 输出；
- 默认严格要求每个样本都有结果；
- 可使用 `--allow-missing` 显式允许缺失，但必须在实验记录中说明测试子集变化。

关键文件：`src/mga/prepare.py`。

### 4.3 原子声明解析

已经提供两类解析器：

1. `heuristic`：确定性规则解析器，用于 CPU 冒烟测试和解析器消融；
2. `openai`：调用 OpenAI-compatible API，以 JSON 结构输出原子声明。

原子声明当前可记录：

- 实体；
- 声明角色：`changed`、`context`、`no_change`；
- 变化类型：`add`、`remove`、`modify`、`unknown`、`none`；
- 位置；
- 数量；
- 属性；
- 目标掩码类别。

解析结果会写回 JSONL，因此正式评分不需要重复调用 LLM。

需要注意：规则解析器仅覆盖有限英文实体和触发词，不应作为论文主实验解析器。

关键文件：`src/mga/parsing/`。

### 4.4 视觉定位与缓存

已经实现统一 `Grounder` 接口和两个后端：

- `metadata`：读取原子声明元数据中预先保存的前、后时相实体掩码，适合单元测试、oracle 实验和离线消融；
- `hf-dino`：通过 Hugging Face Transformers 加载 Grounding DINO，在前、后时相上分别定位声明实体。

Grounding DINO 当前实现会把所有返回框栅格化并合并为二值支持掩码，同时保存：

- 前、后时相最高检测置信度；
- 前、后时相检测框数量；
- 查询实体；
- Grounder 标识和阈值。

磁盘缓存已经实现。缓存键包括 Grounder 标识、样本 ID、前后图像路径和完整原子声明；缓存内容为压缩的 `.npz`，可避免重复定位。

关键文件：`src/mga/grounding/`。

### 4.5 掩码处理

已经实现：

- PNG 等单通道标签掩码和 `.npy` 掩码读取；
- 默认将所有非零像素视为变化；
- 通过 `metadata.mask_labels` 指定多类掩码中的目标类别；
- 4 邻域连通组件提取；
- IoU、support precision、非重叠比例、时序新颖度和时序差异；
- 按连通变化区域计算 coverage；
- MGA v1 所需的“仅保留与真值变化区域相交的预测组件”。

RGB 颜色掩码不会被隐式转换，而是主动报错，避免无声地产生错误标签。

关键文件：`src/mga/mask_ops.py`。

### 4.6 MGA v1 重建

`LegacyMGAScorer` 已实现一个文档化的 MGA v1 重建版本，用于受控对比：

- 变化实体使用 Grounding 支持区域与变化掩码的 IoU；
- 评分前移除所有与真值变化掩码完全不相交的预测组件；
- 上下文实体使用与变化区域的非重叠比例；
- 默认变化实体权重为 `0.7`，上下文权重为 `0.3`；
- 空实体组沿用旧逻辑，得分设为 `1.0`。

该实现的定位是“旧公式重建与消融基线”，目前尚未与丢失前保存的完整 MGA v1 输出逐样本核对，因此不能宣称已经完成数值级复现认证。

关键文件：`src/mga/scoring.py` 中的 `LegacyMGAScorer`。

### 4.7 MGA v2 多维评分

MGA v2 不再只输出一个分数，而是输出以下维度：

| 输出 | 当前实现含义 |
| --- | --- |
| `faithfulness` | 可验证变化声明的空间支持与时序支持加权平均 |
| `coverage` | 被变化声明支持区域覆盖的变化连通组件比例 |
| `temporal` | `add`、`remove` 或 `modify` 是否符合前后时相证据 |
| `context_support` | 上下文实体是否能够被定位；当前以 Grounding 置信度表示 |
| `unverifiable_rate` | 因证据缺失、置信度不足或证据模糊而无法验证的声明比例 |
| `overall` | `faithfulness`、`coverage`、`temporal` 的可选加权汇总 |

每个原子声明还会被分类为：

- `supported`；
- `contradicted`；
- `unverifiable`。

当前主要逻辑包括：

- `add`：后时相存在且变化区域内的证据为正证据，前时相持续存在为反证据；
- `remove`：前时相存在为正证据，后时相持续存在为反证据；
- `modify`：使用前后支持掩码在变化区域内的异或比例；
- `no_change`：直接检查整张变化掩码是否为空；当前仅支持全局无变化声明，不能验证某个局部实体或局部区域“没有变化”；
- 低置信度或目标时相无实体支持：记为 `unverifiable`，而不是直接记错；
- v2 不会在计算空间准确性前删除假阳性预测区域；
- faithfulness 和 coverage 分开报告，避免“描述准确但遗漏大量变化”被一个分数掩盖。

默认阈值和权重已经写在 `MGAV2Config` 中。`configs/mga_v2.json` 目前只是参数样例，CLI 尚未读取该文件。

关键文件：`src/mga/scoring.py`。

### 4.8 受控文本扰动

`mga perturb` 已实现三类初始扰动：

- 注入不存在的变化实体；
- 交换出现/消失等时间方向；
- 交换左右、上下等位置词。

扰动样本会记录原始样本 ID 和扰动类型，可用于检查指标是否满足预期的单调性。

当前只实现了扰动数据生成，尚未实现批量评分后的单调性统计和显著性检验。尤其是位置字段尚未参与评分，因此位置交换当前只用于准备未来实验，不能预期现有 MGA v2 对它稳定降分。

关键文件：`src/mga/perturbations.py`。

### 4.9 命令行与工程基础

当前 CLI 包含：

```text
mga prepare-feedback
mga attach-change-agent
mga validate
mga parse
mga perturb
mga score
```

工程基础已经包括：

- `pyproject.toml` 打包与可编辑安装；
- `dev`、`gpu`、`llm` 可选依赖；
- AutoDL 环境初始化脚本；
- `.env.example`；
- GitHub Actions 多 Python 版本测试；
- README、架构、数据格式和 AutoDL 文档。

当前 `requirements-autodl.txt` 只安装 `gpu` 和 `llm` 依赖，没有安装包含 `pytest`、`ruff` 的 `dev` 依赖。因此现有初始化脚本执行完后，不保证能直接运行部署文档中的测试命令；这是 AutoDL 首次上机前应修正的工程问题。

## 5. 当前验证状态

### 5.1 已通过的自动化验证

现有 9 项单元测试覆盖：

- 正确新增实体时 MGA v2 各维度为满分；
- 无变化场景中，虚构变化声明被判为矛盾；
- MGA v2 不会像 v1 一样预先删除假阳性组件；
- 上下文实体与变化区域相交时不被自动判错；
- 低置信度定位被判为不可验证；
- feedback JSONL 转换和 Change-Agent 文本挂接；
- 无变化和新增描述的规则解析；
- Grounding 缓存保存与恢复。

GitHub CI 已在 Python 3.10、3.11、3.12 上通过 `ruff check .` 和 `pytest`。

### 5.2 尚未完成的验证

以下内容不能因单元测试通过而视为完成：

- AutoDL GPU 上的依赖安装与 CUDA 兼容性；
- Grounding DINO 权重下载、推理和真实遥感图像定位质量；
- 完整数据集端到端运行；
- Grounding 缓存的长期存储、断点续跑和跨实例恢复；
- OpenAI-compatible 解析器在目标服务上的兼容性、失败重试和输出稳定性；
- Draft、Guided、Change-Agent 三组样本集合完全一致；
- MGA v1 与旧实验结果的数值一致性；
- MGA v2 与五人人工评价的相关性和统计显著性；
- 扰动实验是否产生预期的单调降分；
- 不同阈值、Grounder 和解析器选择对结论的敏感性。

## 6. 当前实现边界

### 6.1 已有字段但尚未真正评分

原子声明中的 `location`、`count` 和 `attributes` 已有数据结构，但 MGA v2 当前没有专门验证这些内容：

- 位置词不会与图像坐标或实体间空间关系比较；
- 数量不会与检测实例数比较；
- 属性不会单独验证；
- `context_support` 只验证上下文实体是否被定位，不验证 `near`、`along`、`left of` 等关系。

因此，当前 `spatial_support` 的准确含义是“变化实体支持区域落在变化掩码中的比例”，不是完整的自然语言空间关系正确性。

### 6.2 Grounding DINO 仍是框级掩码

当前后端把矩形检测框直接当作支持掩码，可能产生较大背景面积，从而影响 support precision、coverage 和时序差异。Grounded-SAM 或同类精细分割后端尚未实现。

### 6.3 参数与运行可复现性仍不完整

- `configs/mga_v2.json` 尚未接入 CLI；
- Grounding DINO 模型 revision 尚未固定；当前 backend ID 包含模型 ID 和检测阈值，但不包含模型 revision、dtype 或 Transformers 版本，调参和升级环境时可能误用旧缓存；
- CLI 尚未暴露 box/text threshold 和 MGA v2 阈值；
- parser 模型、prompt 版本和调用参数尚未自动写入每次运行的 provenance；
- 缓存键依赖图像路径，但不包含图像内容校验和；
- 缓存写入不是原子操作，也没有损坏恢复或并发写保护；
- 尚无统一的 `run_manifest.json` 记录完整实验环境。

另外，`parse` 和 `perturb` 当前按原样保留清单中的相对路径。如果把输出 JSONL 写到另一个目录，相对路径可能改变含义；服务器端正式运行前需要统一改写为稳定路径，或在输出时相对于新清单目录重新计算路径。

### 6.4 批量实验与统计尚未实现

- Grounding 当前按样本、声明和时相顺序推理，尚无 batching 或混合精度优化；
- `no_change` 声明也会经过 Grounder，存在不必要的 GPU 调用；
- 评分 JSONL 尚未保存完整 Grounding evidence、后端参数和 cache-hit 信息；
- 结果文件直接以写模式生成，长任务中断后尚无可靠的结果级断点续跑；
- 尚无数据集级汇总命令；
- 尚无 bootstrap 置信区间；
- 尚无模型间配对检验；
- 尚无 Spearman、Kendall 或偏好一致性统计；
- 尚无五人人工评价导入器和评价者一致性分析；
- 尚无 LLM-as-Judge 与人工评价分开报告的分析脚本。

### 6.5 数据集支持仍有限

现有转换器主要针对当前 feedback JSONL、LEVIR-MCI 路径模式和 Change-Agent 单文件输出。SECOND-CC 等数据集适配、RGB 语义掩码映射和数据集校验报告尚未实现。

## 7. AutoDL 后续开发计划

后续任务应按 P0 到 P3 顺序推进。不要在真实推理尚未稳定时直接进行完整数据集正式实验。

### P0：环境、配置和数据闭环

目标：确认当前框架能在一台 AutoDL 实例上稳定跑通 10 个真实样本。

需要完成：

1. 检出 `agent/mga-v2-framework`，或在 Draft PR 合并后改用 `main`；
2. 建立代码、数据和持久化实验产物分离的目录；
3. 修正 AutoDL 安装清单，使其同时安装 `dev`、`gpu`、`llm` 依赖，并记录 CUDA、PyTorch、Transformers 和 GPU 信息；
4. 整理 Draft、Guided、Change-Agent 的统一样本清单；
5. 检查三种模型的样本 ID 集合完全一致；
6. 检查前后图像和变化掩码尺寸一致、掩码值域正确；
7. 将 `configs/mga_v2.json` 真正接入 CLI；
8. 暴露并记录 Grounding DINO 阈值、模型 ID 和 revision；
9. 固定 parser prompt、模型版本和原始解析输出；
10. 对 10 个有代表性的样本执行 validate、parse、score v1 和 score v2。

P0 验收标准：

- `pytest` 和 `ruff check .` 在 AutoDL 上通过；
- `nvidia-smi` 与 PyTorch CUDA 检查通过；
- Draft、Guided、Change-Agent 的 `sample_id` 集合完全相等，并且恰好形成 10 个场景 × 3 个指定模型 = 30 条输入记录；
- v1 和 v2 分别输出 30 条结果，没有静默丢样、重复键、NaN 或 mask shape mismatch；
- `supported`、`contradicted`、`unverifiable` 的数量分布被记录；若全部为同一状态，必须停止并排查；
- 第二次相同配置运行全部命中 Grounding cache，并且评分结果与第一次逐条一致；
- 每次运行保存 Git 提交、依赖、配置、模型 revision 和样本数；
- 人工抽查至少 10 个样本，没有明显的 A/B 时相颠倒或掩码错配。

### P1：真实 Grounding 诊断与精细掩码

目标：确认视觉证据质量足以支持指标计算，而不是只确认程序能够运行。

需要完成：

1. 增加 Grounding 可视化导出，展示前图、后图、变化掩码、检测框和支持掩码；
2. 建立包含新增、移除、修改、无变化、上下文实体和失败案例的诊断子集；
3. 对 box threshold、text threshold 和 `min_grounding_confidence` 做验证集调参；
4. 固定模型 revision，避免权重更新导致结果漂移；
5. 实现 Grounded-SAM 后端，并保持与现有 `Grounder` 接口兼容；
6. 比较 DINO 框掩码、SAM 精细掩码和人工/oracle 掩码的评分差异；
7. 对缺失检测、重复框、超大框、跨时相误匹配和小目标建立错误分类。

P1 验收标准：

- 每类诊断样本均有可视化和人工审查记录；
- 参数只使用验证集选择，不使用正式测试集调参；
- Grounded-SAM 后端通过新增单元测试和小规模 GPU 集成测试；
- 同一配置重复运行得到一致结果；
- 对 Grounding 失败能够区分 `contradicted` 与 `unverifiable`，并有案例说明。

### P2：语义验证和批量实验工程

目标：补齐当前声明字段与实际评分之间的差距，并让完整数据集运行可恢复、可审计。

需要完成：

1. 实现位置和空间关系验证器；
2. 实现数量验证，无法可靠计数时明确 abstain；
3. 实现属性验证或明确把属性标为不可验证；
4. 校准上下文支持度，避免直接把未校准检测置信度当作语义分数；
5. 增加 batching、混合精度和显存控制；
6. 增加断点续跑、失败样本记录和任务恢复；
7. 增加数据集级汇总命令，同时保留原始声明级结果；
8. 将配置、环境和运行信息写入统一 provenance 文件；
9. 增加 CLI 端到端测试、Grounding DINO 集成测试和配置加载测试；
10. 增加 SECOND-CC 或其他目标数据集适配器。

P2 验收标准：

- 位置、数量和属性都有“支持、矛盾、不可验证”的明确处理规则；
- 中断完整实验后能够从最后一个未完成样本继续；
- 错误样本不会导致已完成结果丢失；
- 完整运行可由一个配置文件和一个命令复现；
- 汇总结果可追溯到每条 caption、每个 claim 和对应 Grounding 证据。

### P3：正式指标验证与论文实验

目标：证明 MGA v2 比 MGA v1 更符合人工判断，并量化结论的不确定性。

需要完成：

1. 导入五人逐评价者原始标注，保留匿名评价者 ID；
2. 明确人工评分任务、标签尺度、缺失值和多数票规则；
3. 计算评价者间一致性，并报告分歧样本；
4. 将人工评价、LLM-as-Judge 和 MGA 分开存储、分开统计；
5. 对 MGA v1、MGA v2 各维度和 `overall` 计算相关性；
6. 计算 bootstrap 置信区间和模型间配对检验；
7. 执行实体注入、时间方向交换和位置交换的单调性实验；
8. 进行 parser、Grounder、阈值、权重和 SAM 的消融实验；
9. 在 Draft、Guided、Change-Agent 完全相同的样本集合上比较；
10. 固化正式实验配置、随机种子、环境和输出表格。

P3 验收标准：

- 五人人工评价与 LLM-as-Judge 不发生字段或统计口径混用；
- 报告逐维指标、总体指标、置信区间和样本数；
- 扰动后的指标变化方向符合预注册预期，异常案例有解释；
- MGA v2 相对 v1 的改进有统计证据，而不只依赖少数案例；
- 所有论文表格都能从保存的原始结果通过脚本重新生成。

## 8. AutoDL 首次运行建议

### 8.1 推荐目录

```text
/root/autodl-tmp/MGA/               # Git 代码
/root/autodl-tmp/datasets/          # 图像和掩码
/root/autodl-tmp/mga-artifacts/
  manifests/                        # 规范化清单
  claims/                           # 固定的原子声明
  grounding-cache/                  # 昂贵的视觉定位缓存
  overlays/                         # 人工审查可视化
  scores/                           # v1/v2 原始结果
  summaries/                        # 数据集级统计
  logs/                             # 环境和运行日志
```

如果实例磁盘会随关机或到期释放，应把 `mga-artifacts` 放在持久化存储，或在每次运行后同步到不会随实例丢失的位置。

### 8.2 首次命令顺序

```bash
git clone --branch agent/mga-v2-framework \
  https://github.com/IreliaNeu/MGA.git
cd MGA
git checkout fb6d694
bash scripts/setup_autodl.sh
source .venv/bin/activate

# 在部署脚本正式补入 dev 依赖前，临时执行：
python -m pip install -e ".[dev]"

pytest
ruff check .
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"

mga prepare-feedback \
  --input /path/to/feedback_results.jsonl \
  --output /path/to/mga-artifacts/manifests/feedback.jsonl \
  --mask-root /path/to/datasets/LEVIR-MCI/masks/test

mga attach-change-agent \
  --manifest /path/to/mga-artifacts/manifests/feedback.jsonl \
  --results-dir /path/to/change_agent_results \
  --output /path/to/mga-artifacts/manifests/all_models.jsonl

mga validate \
  --manifest /path/to/mga-artifacts/manifests/all_models.jsonl
```

随后先截取 10 个代表性样本生成 smoke manifest，再执行原子声明解析和 v1/v2 评分。不要直接把完整测试集作为第一次 Grounding DINO 运行。

### 8.3 每次正式运行必须保存

- Git commit 和分支；
- 命令行与完整配置；
- `python --version`、`pip freeze`、`nvidia-smi`；
- CUDA、PyTorch、Transformers 版本；
- parser 模型、endpoint、prompt 版本和解析原文；
- Grounding 模型 ID、revision 和阈值；
- 数据集版本、样本 ID 清单、样本数和可用校验和；
- Grounding cache；
- 声明级原始评分；
- 聚合脚本产生的统计结果；
- 错误样本和人工审查记录。

API key、私有数据、模型权重和大体积缓存不得提交到 Git 仓库。

## 9. 建议的近期开发顺序

AutoDL 开机后的近期工作建议严格按以下顺序执行：

1. 跑通环境和 10 样本真实数据闭环；
2. 修复配置加载、模型 revision 和 provenance；
3. 增加 Grounding 可视化并人工审查定位质量；
4. 调整 Grounding 阈值并建立错误分类；
5. 实现 Grounded-SAM；
6. 为完整数据集加入 batching、恢复和失败记录；
7. 再运行 Draft、Guided、Change-Agent 完整实验；
8. 最后接入五人人工评价、统计检验和论文表格。

该顺序的核心原则是：先确认数据对齐和视觉证据可信，再扩大计算规模；先保存声明级原始证据，再进行模型级汇总。

## 10. 阶段结论

当前项目已经从“旧代码丢失”恢复为结构清晰、可测试、可扩展的 MGA v1/v2 研究框架。数据转换、原子声明、Grounder 接口、缓存、核心评分、扰动生成、CLI、测试和 AutoDL 基础文档均已具备。

当前仍不能视为正式实验完成。最关键的缺口不是再增加公式，而是完成真实遥感数据上的 GPU 验证、Grounding 质量诊断、配置与 provenance 固化、Grounded-SAM、批量恢复能力，以及五人人工评价驱动的统计验证。完成 P0 和 P1 后，只适合开展受控的小规模试运行；完成 P2 的配置固化、语义规则、断点恢复和批量工程后，才适合启动正式全量计算；完成 P3 后，才适合形成论文中的最终指标结论。
