# AutoDL 环境激活与单样例测试

> 2026-09-06 更新：当前 43850 实例挂载的是较早数据盘快照。最新代码和8月实验汇总以本地工作区为准；服务器差异见 `docs/autodl-current-state-2026-09-06.zh-CN.md`。下文保留早期环境搭建记录，不再作为当前完整实验状态说明。

本文记录当前 MGA 项目在 AutoDL 服务器上的实际配置，用于从本地 Codex、
VS Code Remote SSH 或普通终端快速恢复开发和测试。

## 1. 登录服务器

在本地 PowerShell 中执行：

```powershell
ssh -p 43850 root@connect.bjb1.seetacloud.com
```

当前已配置 SSH 公钥登录，不应把私钥、服务器密码或 API Key 写入项目。
AutoDL 实例重启或更换后，公网端口可能变化；如登录失败，应先在 AutoDL
控制台核对最新 SSH 指令。

## 2. 激活 Conda 环境

登录服务器后执行：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA
```

提示符前出现 Conda 环境标记后，可检查当前解释器：

```bash
which python
python --version
python -c 'import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))'
```

当前已验证的关键环境为：

- Python 3.11.15；
- PyTorch 2.11.0+cu130；
- CUDA runtime 13.0；
- NVIDIA GeForce RTX 4090；
- `torch.cuda.is_available()` 为 `True`。

如果不希望激活环境，也可使用以下形式运行任意命令：

```bash
/root/miniconda3/bin/conda run \
  -p /root/autodl-tmp/conda-envs/mga \
  python --version
```

## 3. Git 与基础测试

```bash
cd /root/autodl-tmp/MGA
git status --short --branch
git pull --ff-only
pytest -q
ruff check .
mga --help
```

当前服务器项目位于 `agent/mga-v2-framework` 分支，已验证 9 项测试全部通过，
ruff 无报错。运行实验前应确认工作区没有意外修改，并记录实际 commit：

```bash
git rev-parse HEAD
```

## 4. Hugging Face 学术资源加速

只有在下载 Hugging Face 模型或访问 GitHub 时才启用 AutoDL 学术加速：

```bash
source /etc/network_turbo
```

该设置只对当前 Shell 生效，而且可能拖慢普通 pip 源，因此不要在普通依赖安装
期间长期启用。当前 Conda 环境已配置以下持久化变量：

```text
HF_HOME=/root/autodl-tmp/mga-artifacts/hf-cache
HUGGINGFACE_HUB_CACHE=/root/autodl-tmp/mga-artifacts/hf-cache/hub
HF_HUB_DISABLE_XET=1
MGA_ARTIFACTS_DIR=/root/autodl-tmp/mga-artifacts
```

`HF_HUB_DISABLE_XET=1` 用于避开公开模型通过 Xet CAS 下载时出现的 401 问题。
当前 `IDEA-Research/grounding-dino-tiny` 已完整缓存。复跑已缓存模型时可临时
启用离线模式，避免不必要的 Hub 网络检查：

```bash
export HF_HUB_OFFLINE=1
```

需要下载新模型时，先执行：

```bash
unset HF_HUB_OFFLINE
source /etc/network_turbo
```

## 5. 复跑当前一条测试样例

服务器已准备一张公开 COCO 测试图、一张空变化掩码和一条测试 manifest：

```text
/root/autodl-tmp/mga-artifacts/smoke/cats.jpg
/root/autodl-tmp/mga-artifacts/smoke/empty_change_mask.png
/root/autodl-tmp/mga-artifacts/smoke/manifest.jsonl
```

先验证输入文件：

```bash
cd /root/autodl-tmp/MGA
mga validate \
  --manifest /root/autodl-tmp/mga-artifacts/smoke/manifest.jsonl
```

再使用 GPU 上的 Grounding DINO 执行 MGA v2 评分：

```bash
HF_HUB_OFFLINE=1 mga score \
  --manifest /root/autodl-tmp/mga-artifacts/smoke/manifest.jsonl \
  --output /root/autodl-tmp/mga-artifacts/scores/smoke_v2.jsonl \
  --method v2 \
  --grounder hf-dino \
  --device cuda \
  --cache-dir /root/autodl-tmp/mga-artifacts/grounding-cache
```

查看输出：

```bash
wc -l /root/autodl-tmp/mga-artifacts/scores/smoke_v2.jsonl
python -m json.tool \
  /root/autodl-tmp/mga-artifacts/scores/smoke_v2.jsonl
```

预期结果是 manifest 包含 1 条记录、评分输出包含 1 行。当前验证中 Grounding
DINO 检测到 2 个猫框，最高置信度约为 0.814，峰值显存约为 1.75 GB。

## 6. 切换到真实的 1 至 10 条样例

目前服务器尚未放置正式遥感图像、变化掩码以及 Draft、Guided、Change-Agent
结果，所以还不能直接运行真实小批量。准备数据时建议将其放在持久盘，而不是
Git 仓库或系统盘：

```text
/root/autodl-tmp/datasets/                 # 图像和变化掩码
/root/autodl-tmp/mga-artifacts/manifests/  # 规范化 manifest
/root/autodl-tmp/mga-artifacts/scores/     # 评分输出
/root/autodl-tmp/mga-artifacts/logs/       # 日志
```

真实 manifest 每条记录至少需要：

- `sample_id`；
- `model`；
- `caption`；
- `pre_image`；
- `post_image`；
- `change_mask`；
- 非空的 `claims`。若没有 claims，先运行 `mga parse`。

建议按以下顺序扩大规模：

1. 用 `mga validate` 检查全部路径；
2. 只截取 1 条记录运行；
3. 确认输出和 Grounding 缓存正常；
4. 扩大到 10 条代表性记录；
5. 最后才运行完整数据集。

Grounding 缓存目录应始终使用持久盘：

```text
/root/autodl-tmp/mga-artifacts/grounding-cache
```

## 7. 常见问题

### Hugging Face 出现 Xet 401

```bash
export HF_HUB_DISABLE_XET=1
source /etc/network_turbo
```

### 已缓存模型仍尝试联网且失败

```bash
export HF_HUB_OFFLINE=1
```

### CUDA 不可用

```bash
nvidia-smi
python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
```

### manifest 提示没有 claims

```bash
mga parse \
  --manifest /path/to/input.jsonl \
  --output /root/autodl-tmp/mga-artifacts/manifests/claims_smoke.jsonl \
  --parser heuristic
```

启发式 parser 只适合检查流程。正式实验应使用固定模型、固定提示词并持久化的
LLM claims。
