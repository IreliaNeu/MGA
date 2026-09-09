# MGA 项目 Agent 协作指南

## 适用范围

本文件适用于整个仓库。若子目录中存在更具体的 `AGENTS.md`，则以距离目标文件
最近的说明为准。

MGA 是面向开放式遥感变化描述的双时相证据评价研究工具。任何工作都应优先保证
实验可复现、论文主张准确，并保护已有代码、数据与研究产物。

## 开始工作前

修改代码、实验或论文之前，按任务需要阅读：

1. `README.md`
2. `docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md`
3. `docs/server-recovery-audit-2026-09-06.zh-CN.md`
4. 服务器任务阅读 `docs/autodl-current-state-2026-09-06.zh-CN.md`
5. 分数定义阅读 `docs/mga-three-mode-calculation.zh-CN.md`

如果文档互相冲突，以最新交接文档和 `artifacts/**/summary.json` 中的紧凑结果为准。
无法确认时应明确报告冲突，不要自行选择更有利的数字。

## 研究主线

实现与论文必须围绕以下主张展开：

> MGA 将候选描述拆成原子变化 Claim，并检查其能否得到双时相视觉 Evidence 支持；
> 它用于补充参考文本相似度，而不是取代所有语言质量指标。

保留并正确区分三种模式：

- `MGA-Hybrid`：论文主方法；按标注可用性路由可靠语义证据与开放词汇证据。
- `MGA-GT`：语义标签 oracle 或理想上界，不是无参考、无标注设置。
- `MGA-OV`：开放词汇压力测试，也是当前真实无标注部署的保守下界。

必须显式保留 `supported`、`contradicted`、`unverifiable` 三态。优先报告
faithfulness、coverage、temporal、spatial/context support 和 unverifiable rate
组成的分量向量，不要用未经校准的单一 Overall 覆盖诊断信息。

不得声称现有证据已经证明：

- MGA Overall 与人工总体判断高度一致；
- MGA 全面优于所有事实评价基线；FMScore-Qwen 仍具有竞争力；
- Predicted ROI 提高了总体 AUC；
- 开放式 QA 适配已经验证成功；
- 纯 reference-free 视觉证据可以发现描述遗漏；
- 纯开放词汇定位已经足以可靠部署。

当前投稿最主要的未完成项是独立 held-out 人工效度实验。

## 仓库结构

- `src/mga/`：可复用库与 CLI 实现。
- `tests/`：CPU 单元测试与回归测试。
- `scripts/`：实验构造、评价、统计分析和可视化入口。
- `configs/`：Parser 本体、同义表达、类别映射和语义调色板。
- `artifacts/`：可公开的小型 JSON/CSV/Markdown 汇总。
- `paper/`：论文段落、审计记录和投稿图表。
- `docs/`：实验归档、服务器说明和交接记录。
- `sources/`：文献与来源记录。
- `examples/`：适合 smoke test 的小型公开输入。

## 环境与常用命令

项目支持 Python 3.10–3.12。存在已配置环境时优先复用。

Windows 本地验收：

```powershell
D:\miniconda3\envs\mga\python.exe -m pytest -q
D:\miniconda3\envs\mga\python.exe -m ruff check src tests
D:\miniconda3\envs\mga\python.exe -m mga.cli --help
```

通用安装与验收：

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check src tests
```

当前已接受基线为：93 项测试通过，`ruff check src tests` 通过（2026-09-08；恢复时为 76 项）。

注意：2026-09-07 将 CI 的 Ruff 范围调整为 `src tests` 加本次四个分析/审计入口，
并增加论文源表一致性检查。历史一次性脚本仍有格式问题，不能称全仓库 Ruff-clean。
本地检查不代表远端 CI；发布后仍须检查对应提交的远端运行。

2026-09-08 起优先使用 `python scripts/validate_project.py` 统一验收；服务器加 `--server`。
CI 使用同一入口，维护脚本列表集中在该文件的 `ENTRYPOINTS` 中。

## 修改流程

1. 编辑前运行 `git status --short --branch`。
2. 保留用户已有修改和无关的未跟踪研究文件。
3. 使用小而可审查的补丁，除非用户要求，不做大范围机械重写。
4. 修改 `src/mga/` 的可复用逻辑时同步增加或更新测试。
5. 开发中先运行相关测试，交付前运行完整测试集和 `ruff check src tests`。
6. 运行 `git diff --check` 并检查最终差异。
7. 行为、路径、协议、哈希或论文主张变化时，同步更新相关实验或交接文档。

不得为了改善结果而直接修改评分公式。公式变化必须有版本化协议、相应测试和新的
实验目录，不能覆盖历史结果。

## 实验完整性

- 记录数据集与 split、场景数、随机种子、阈值、class map、模型/后端版本、输入
  哈希和输出哈希。
- 校准集与测试集必须按 scene/group 隔离；阈值只能在 development 数据上选择。
- 保留历史结果，新实验写入新的版本化目录。
- 文件名与报告中区分真实模型输出、受控扰动、oracle 证据和缓存结果。
- `unverifiable` 是独立结果，不能默认等同于 0 或 contradiction；如果计算 AUC 时
  映射为中性值 0.5，必须明确说明。
- 如实报告负结果和实现替代，包括 FMScore 的 Qwen 适配与 ALOHa local variant。
- 不得从聚合均值推断显著性；比较性主张优先采用 scene-level paired bootstrap CI。
- 已有可靠紧凑汇总与哈希时，不要仅为了恢复目录外观而重跑 GPU 大模型。

若没有明确创建新版本，SECOND-CC 重建保持归档协议：按文件名排序的前 600 个候选、
选择 200 个场景、`min_pixels=64`、`seed=20260726`。

## 数据与产物规则

严禁提交：

- 私钥、密码、令牌、`.env*` 中的密钥或 SSH 凭据；
- 已填写或原始人工评价工作簿（`*.xlsx`）；
- 数据集、模型权重、checkpoint、缓存或临时下载；
- 逐样本原始 JSONL 和大批逐场景可视化。

Git 可以保存面向论文的小型 JSON/CSV/Markdown 汇总和选定总览图。原始数据放在
持久存储，并在 `docs/` 或紧凑 manifest 中记录来源与哈希。本地归档默认只保留
总览，除非用户明确要求逐样本文件。

删除已上传压缩包之前，必须验证哈希、解压文件数、必要元数据和下游重建产物；
删除时只操作已经解析并确认的精确路径。

## AutoDL 操作

不要假设 AutoDL 实例正在运行，也不要假设历史 SSH 端口仍然有效。只使用用户当前
提供的登录命令和公钥认证，绝不把私钥材料写入项目。

恢复后的预期路径为：

```text
/root/autodl-tmp/MGA-current
/root/autodl-tmp/conda-envs/mga
/root/autodl-tmp/datasets
/root/autodl-tmp/mga-artifacts
```

旧目录 `/root/autodl-tmp/MGA` 仅用于历史追溯，不能覆盖本地工作区。服务器环境：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA-current
```

只有访问 GitHub 或 Hugging Face 需要加速时才执行 `source /etc/network_turbo`。
数据集、缓存和权重必须放在数据盘。

执行用户已授权的关机前，检查代码状态、测试、产物哈希与数量、剩余空间和文档；
运行 `sync` 后再关机，并记录后续 SSH 是否拒绝连接。

## 论文与文档

- 操作说明和实验记录默认使用中文；目标论文段落明确要求时使用英文或双语。
- 固定使用 Claim、Evidence、MGA-Hybrid、MGA-GT、MGA-OV、coverage、false
  support rate 和 unverifiable rate 等术语。
- 每项数值主张都应指向已跟踪的 summary 或人工评价记录。
- 新紧凑汇总存在时，不要从旧叙述文档直接复制数字。
- Parser 错误、语义标签缺失、omission、Predicted ROI 和开放词汇召回等限制应紧邻
  对应主张说明。
- 外部事实与相关工作只使用可核验的一手来源并给出引用。

## Git 与外部操作

- 用户要求实现或归档时，可以创建本地提交。
- 未获得对目标和载荷的明确授权，不得推送公开仓库、发布产物、发送外部消息或创建
  release。
- 除非用户明确要求，不得改写共享历史或执行破坏性 Git 操作。
- 即使用户授权公开推送，也不能把原始研究数据和个人评价文件加入公开提交。

## 完成标准

只有满足以下条件，任务才算完成：

- 请求的代码、分析或文档已写入正确位置；
- 相关测试和核心 lint 通过，或失败被准确记录；
- 适用时已记录实验输入、协议参数和哈希；
- 未意外加入密钥、私人评价、权重、数据集或临时下载；
- 上传、清理、关机等状态变化已经验证；
- 最终交接明确区分已完成内容、剩余限制和仍需用户授权的动作。
