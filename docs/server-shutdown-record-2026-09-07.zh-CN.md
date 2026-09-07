# AutoDL 恢复与关机记录（2026-09-07）

- 实例入口：`ssh -p 43850 root@connect.bjb1.seetacloud.com`
- 容器：`autodl-container-c5b149a521-2578d934`
- 恢复验收时间：2026-09-07 10:22（Asia/Shanghai）
- 用户授权：完成恢复、保存记录并更新交接文档后关闭服务器。

## 关机前验收

- 当前工作区：`/root/autodl-tmp/MGA-current`；旧 `MGA` 目录未覆盖。
- 冻结基线：`68f63354a25fa8b3bdcd01e12b3fe44f65a46cdd`；恢复文档提交位于其后。
- MGA 环境解析到 `MGA-current/src/mga`。
- 回归测试：76 passed。
- 静态检查：`ruff check src tests` passed。
- CLI 与 smoke manifest：通过。
- SECOND-CC：四个测试目录各 1,227 张 PNG，解压数据约 4.3 GiB。
- 重建输入：事实图 200 行、基础样本 600 行、Parser 样本 1,200 行、最小错误 1,600 行。
- benchmark manifest SHA-256：`36ed910f1eff3506b02077fb8122a9f4682d2cd95c1c20cab7c2f9d58acd43c5`，与本地归档一致。
- Caption 框架：Chg2Cap `7b8cda9`、RSICC `d1505e5`；未下载权重、未重复推理。
- 本地下载 ZIP、分段文件和临时下载脚本已清理；服务器上传 ZIP 已清理。
- 数据盘：约 30/50 GiB 已用，约 21 GiB 可用。

## 关机动作

本记录和交接文档同步到服务器并完成最后一次只读核验后，依次执行：

```bash
sync
shutdown -h now
```

SSH 连接断开是预期结果。再次使用时应从 AutoDL 控制台启动实例，并先阅读：

- `docs/autodl-current-state-2026-09-06.zh-CN.md`
- `docs/server-recovery-audit-2026-09-06.zh-CN.md`
- `docs/project-progress-gpt6-astra-handoff-2026-09-06.zh-CN.md`
