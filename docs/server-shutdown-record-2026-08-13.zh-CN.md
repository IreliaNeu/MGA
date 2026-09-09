# AutoDL 关机记录（2026-08-13）

本轮 Grounding DINO Base/Tiny 500 场景消融、ALOHa-local、FMScore-Qwen、统一事实错误比较和遥感描述复合指标实验已完成。

关机前核验：

- 服务器完整实验目录：`/root/autodl-tmp/mga-artifacts/p0-1-unified-baselines-20260813/`；
- 本地仅同步 8 个汇总/索引 JSON 和 1 张 Base/Tiny 总览图；
- 本地与服务器上述 9 个产物的 SHA-256 逐项一致；
- 本地归档含 `SHA256SUMS.txt`；
- AutoDL 数据盘剩余约 6.5 GB，系统盘剩余约 18 GB；
- 关机前 `nvidia-smi --query-compute-apps` 无活动 GPU 进程；
- 论文实验增补、完整中文分析和文献来源记录均已写入本地，并同步到服务器项目副本；
- 完成检查后执行 `shutdown -h now`。

