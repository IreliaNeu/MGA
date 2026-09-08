# 统一验收、本地保存与手动推送

本次仅准备 GitHub 命令，公开推送由用户手动执行。服务器使用最近确认的 43850 端口、
`/root/autodl-tmp/MGA-current` 与已有 conda 环境。本地为论文汇总及人工原始表的权威来源。

## Windows 验收

```powershell
Set-Location D:\Python_Practice\MGA
D:\miniconda3\envs\mga\python.exe scripts/validate_project.py --output outputs/acceptance-local-01.json
if ($LASTEXITCODE -ne 0) { throw '验收未通过，请检查 JSON 报告' }
```

每次使用新的输出文件名。默认每个检查最多 300 秒，可用 `--timeout` 调整。
完整门槛包括核心及维护入口 Ruff、全部 CPU 测试、论文源表一致性、CLI 和差异空白检查。
脚本执行完所有检查，记录失败，再返回非零退出码；不会因仅打印错误却退出 0 而误报成功。

## AutoDL 验收

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA-current
python scripts/validate_project.py --server --output /root/autodl-tmp/mga-artifacts/acceptance/server-01.json
```

`--server` 还检查五份恢复输入的哈希/行数、四个数据子目录各 1227 PNG、包安装路径及
smoke manifest。缺失必要输入、错误包路径或子检查失败都会阻断验收。
GPU 状态与未恢复逐条模型输出只作信息记录，不用它们判定 CPU 框架是否可用。
原审计入口 `python scripts/audit_server_recovery.py --run-checks` 也保留，现已具有失败退出码。

新增回归测试验证：超时、报告拒绝覆盖、恢复输入/包位置错误，以及人工统计 CLI 从输入
到 JSON 的完整链路。测试标签均为临时合成数据，不归档为人工实验结果。

## 本地框架保存

使用 Git bundle 保存已提交历史，使用 archive 保存当前提交的可展开源文件：

```powershell
Set-Location D:\Python_Practice\MGA
$mgaStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$mgaBackup = "D:\Python_Practice\MGA-backups\$mgaStamp"
New-Item -ItemType Directory -Path $mgaBackup | Out-Null
git bundle create "$mgaBackup\MGA-all.bundle" --all
if ($LASTEXITCODE -ne 0) { throw 'bundle 创建失败' }
git bundle verify "$mgaBackup\MGA-all.bundle"
if ($LASTEXITCODE -ne 0) { throw 'bundle 校验失败' }
git archive --format=zip --output="$mgaBackup\MGA-source.zip" HEAD
if ($LASTEXITCODE -ne 0) { throw '源文件归档失败' }
Get-FileHash "$mgaBackup\MGA-all.bundle","$mgaBackup\MGA-source.zip" -Algorithm SHA256
```

bundle/archive 只保护已提交框架。它们不包含忽略的人工 XLSX、逐条 JSONL、数据集与权重；
这些文件仍需另行持久备份。同一磁盘上的副本可以恢复误改，不能抵御磁盘损坏。
从 bundle 恢复时使用新目录，不能覆盖当前本地工作区：

```powershell
git clone '<备份绝对路径>\MGA-all.bundle' D:\Python_Practice\MGA-restore-check
```

## 用户手动推送 GitHub

目标：`https://github.com/IreliaNeu/MGA.git`，分支 `agent/mga-v2-framework`，现有 Draft PR #1。
不需要合并 main 或强制推送。GitHub CLI 的 API 登录成功不代表 Git HTTPS 网络已经可用。

```powershell
Set-Location D:\Python_Practice\MGA
git status --short --branch
git remote -v
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '网络或认证失败，请先恢复连接' }
git log --oneline origin/agent/mga-v2-framework..HEAD
git merge-base --is-ancestor origin/agent/mga-v2-framework HEAD
if ($LASTEXITCODE -ne 0) { throw '远端有未整合提交，请停止并核对，勿 force push' }
D:\miniconda3\envs\mga\python.exe scripts/validate_project.py
if ($LASTEXITCODE -ne 0) { throw '本地验收失败' }
git push origin HEAD:refs/heads/agent/mga-v2-framework
if ($LASTEXITCODE -ne 0) { throw '推送失败，保留完整错误信息' }
git ls-remote origin refs/heads/agent/mga-v2-framework
git rev-parse HEAD
gh run list --repo IreliaNeu/MGA --branch agent/mga-v2-framework --limit 5
```

比较远端与本地 SHA，再检查对应 SHA 的 Python 3.10/3.11/3.12 CI；如有两次 push/PR
触发的工作流，应分别核对。以上不自动修改 PR 描述或将其从 Draft 转为正式审阅。

此前失败原因：本机代理 `127.0.0.1:7890` 未运行，直连也失败，服务器加速返回 503。
如果当前代理已启动，直接使用上面的命令。若代理换端口，可仅对单次命令设置：

```powershell
# 将 7890 改为你实际运行的 HTTP 代理端口；fetch 与 push 使用同一设置。
git -c http.proxy=http://127.0.0.1:7890 fetch origin
git -c http.proxy=http://127.0.0.1:7890 push origin HEAD:refs/heads/agent/mga-v2-framework
```

只有网络恢复后 Git 明确提示认证失败时才重新登录。不要把令牌写入 remote URL 或项目文件。

## 未完成的科研工作

统一验收不替代独立人工效度。约 200 样本的单位与分配、五人标注规则、真实输出备份、
Oracle Claim 对照仍按[后续清单](non-human-work-completion-2026-09-07.zh-CN.md)推进。
本轮没有修改评分公式、历史实验数值或人工表。
