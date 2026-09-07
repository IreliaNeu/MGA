# AutoDL 当前实例状态与恢复结果（更新于 2026-09-07）

> 本文件记录 43850 实例在本轮恢复后的状态。恢复前的三端差异、执行过程和
> 校验值见 `docs/server-recovery-audit-2026-09-06.zh-CN.md`。

## 登录与关机状态

本轮使用的入口为：

```powershell
ssh -p 43850 root@connect.bjb1.seetacloud.com
```

本机公钥登录已验证成功。项目中只记录连接命令，不保存私钥、密码或访问令牌。
本轮恢复完成并同步文档后执行关机；再次使用前需先在 AutoDL 控制台启动实例，
并核对公网端口是否变化。

## 恢复后的代码与环境

- 容器：`autodl-container-c5b149a521-2578d934`；
- GPU：NVIDIA GeForce RTX 4090，24564 MiB；
- 当前项目：`/root/autodl-tmp/MGA-current`；
- 历史项目：`/root/autodl-tmp/MGA`，仅保留追溯，不作为开发入口；
- 分支：`agent/mga-v2-framework`；
- 冻结基线：`68f63354a25fa8b3bdcd01e12b3fe44f65a46cdd`，恢复记录提交位于其后；
- 环境：`/root/autodl-tmp/conda-envs/mga`，Python 3.11.15；
- `mga` 可编辑安装已指向 `/root/autodl-tmp/MGA-current/src/mga`；
- 回归测试：76 passed；
- 静态检查：`ruff check src tests` 通过；
- CLI 与旧 smoke manifest 校验通过。

历史一次性实验脚本尚有 Ruff 格式问题，因此当前质量门槛不是
`ruff check .`。这不影响核心包、测试和已归档结果，但若计划正式发布代码，
应另开任务清理脚本格式。

## 已恢复数据与可复现输入

### SECOND-CC

- 官方归档：`SECOND-CC-AUG.zip`；
- 字节数：2,539,187,782；
- MD5：`ca930ddb819d68a797938b940d1711f1`；
- SHA-256：`2c6743084aa588bd9004b96aac3debe32382f2ce7993ade0f25de11b5414dd83`；
- 解压目录：`/root/autodl-tmp/datasets/SECOND-CC/extracted/SECOND-CC-AUG`；
- `test/rgb/A`、`rgb/B`、`sem/A`、`sem/B` 各 1,227 张 PNG；
- 解压数据约 4.3 GiB；
- 前 600 对类别 ID 标签：`/root/autodl-tmp/datasets/SECOND-CC/decoded-ids`。

下载 ZIP 已在本地和服务器两端完成校验后删除，只保留解压数据、官方哈希和
恢复记录，避免重复占用约 2.54 GB。

确定性重建结果：

```text
/root/autodl-tmp/mga-artifacts/semantic-eval/second-cc-200-v1
  fact_graphs.jsonl             200 行
  evaluation_samples.jsonl      600 行
  parser_all_samples.jsonl     1200 行

/root/autodl-tmp/mga-artifacts/controlled-errors/second-cc-200-v1
  minimal_error_manifest.jsonl 1600 行
```

重建后的 benchmark manifest SHA-256 为
`36ed910f1eff3506b02077fb8122a9f4682d2cd95c1c20cab7c2f9d58acd43c5`，
与本地历史归档完全一致；20 种转移计数、200/600 样本规模和拒绝数 67 也一致。

### Caption 模型框架

只恢复官方代码与目录骨架，不重复下载权重或运行生成模型：

- Chg2Cap：`/root/autodl-tmp/caption-bench-20260808/repos/Chg2Cap`，提交
  `7b8cda937002e614d51a6dab3d949aa7de77c176`；
- RSICC：`/root/autodl-tmp/caption-bench-20260808/repos/RSICC`，提交
  `d1505e514c450c3728782ca723e82761e70bafd3`；
- `incoming/`、`outputs/`、`mga-eval/` 目录已建立。

本地已保存 RSICCformer/Chg2Cap 的汇总、验证信息和原始输出哈希，因此本轮按
用户要求不重跑模型。后续只有在需要逐样本显著性分析且无法从备份找回 JSONL
时，才上传权重并复现推理。

### 仍保留的原有资产

- LEVIR-MCI 原始 ZIP 与整理后的 1000 场景；
- SegEarth-OV-3 仓库、环境和 `sam3.pt`；
- Grounding DINO Tiny 缓存；
- 7 月的 SegEarth 掩膜、Grounding 框和人工 pilot 明细。

## 未恢复但不阻塞当前写作的内容

- 1000 场景 × 5 模型的统一逐条 manifest 与完整 Claim JSONL；
- RSICCformer/Chg2Cap 原始输出 JSONL 和模型权重；
- ALOHa-local、FMScore-Qwen、DINO Base 的逐样本输出与大量逐场景图；
- SECOND-CC 的 SegEarth 缓存和逐样本重评分结果。

这些内容的论文级汇总、哈希和总览已经纳入本地 Git 冻结提交。当前最优先工作
仍是独立人工效度与论文合并；不要仅为了恢复目录外观而重复跑大模型。

## 下次启动后的最小检查

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA-current
git status --short --branch
pytest -q
ruff check src tests
mga validate --manifest /root/autodl-tmp/mga-artifacts/smoke/manifest.jsonl
```

完整项目状态与论文叙述边界见
`docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md`。
