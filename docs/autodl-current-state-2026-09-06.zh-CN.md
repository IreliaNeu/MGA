# AutoDL 当前实例状态（2026-09-06）

> 本地、服务器与 GitHub 的逐项比较、恢复优先级和关键文件哈希见 `docs/server-recovery-audit-2026-09-06.zh-CN.md`。

## 登录

用户确认的当前命令：

```powershell
ssh -p 43850 root@connect.bjb1.seetacloud.com
```

本机公钥登录已验证成功。不要在项目中记录私钥、密码或访问令牌。

## 当前资源

- 容器：`autodl-container-c5b149a521-2578d934`
- GPU：NVIDIA GeForce RTX 4090，24564 MiB；检查时空闲。
- 系统盘：30 GB，约 29 GB 可用。
- 数据盘：50 GB，约 26 GB 可用。
- 项目分支：`agent/mga-v2-framework`
- 服务器 HEAD：`7b48834`
- 服务器回归测试：36 passed。
- 环境：`/root/autodl-tmp/conda-envs/mga`（Python 3.11.15）和 `segearth-ov3`（Python 3.12.13）。

## 数据盘实际内容

全盘搜索确认当前实例只保留较早阶段：

- LEVIR-MCI 原始 ZIP 约 2.6 GB；
- 已整理 LEVIR-MCI 1000 场景约 308 MB；
- SegEarth-OV-3 约 3.3 GB；
- Grounding DINO Tiny HF 缓存约 659 MB；
- 7 月 24 日以前的 SegEarth、证据模式和50场景人工pilot产物。

以下 8 月关键目录在当前数据盘中不存在，且未发现 ZIP/TAR 备份：

```text
/root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1
/root/autodl-tmp/mga-artifacts/p0-1-unified-baselines-20260813
/root/autodl-tmp/caption-bench-20260808
/root/autodl-tmp/datasets/SECOND-CC
```

也未搜索到：

- `external-metric-comparison.json`；
- `segearth_unified_1000_summary.json`；
- `minimal_error_manifest.jsonl`；
- `grounding-dino-size-ablation.json`；
- RSICCformer 最佳 checkpoint。

## 与本地的差异

本地 `D:\Python_Practice\MGA` 是更新后的权威工作区：76 tests，包含8月实验脚本、论文、汇总 artifacts 和强事实基线。当前服务器只有36 tests，缺少后续新增模块与明细数据。

禁止操作：

- 不要从服务器执行覆盖式 `scp`/`rsync` 到本地；
- 不要将当前服务器缺少的目录解释为实验从未完成；
- 不要覆盖服务器旧项目后再试图恢复差异。

推荐恢复方式：

1. 先在本地完成一次“实验冻结”提交；
2. 将最新项目同步到服务器的新目录或先备份旧项目；
3. SECOND-CC、Caption Bench 和逐样本实验明细从原持久盘/备份恢复；若无法恢复，只重跑后续论文真正需要的最小集合；
4. 用本地 `artifacts/**/summary.json` 和 SHA-256 作为重跑验收依据。

## 接续入口

完整项目状态、实验数值和 GPT-6 Astra 提示见：

`docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md`
