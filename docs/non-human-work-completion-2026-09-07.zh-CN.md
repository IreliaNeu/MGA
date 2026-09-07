# 非人工工作验收与后续清单（2026-09-07）

## 范围与主线

本轮延续 9 月 6 日恢复工作。本地 `D:\Python_Practice\MGA` 仍是论文数值及人工原始表的
权威来源；服务器入口仅为 `/root/autodl-tmp/MGA-current`。MGA-Hybrid 是主方法，
通过双时相 Claim—Evidence 验证补充参考文本指标；MGA-GT 是理想语义证据条件，
MGA-OV 是开放后端压力测试。独立人工评价仍未完成。

## 已完成

1. **服务器恢复审计。** 使用用户确认的 SSH 端口 43850。恢复输入的五个哈希与恢复记录
   一致，事实图/基础评价/Parser/扰动分别为 200/600/1200/1600 条，SECOND 测试数据的
   RGB A/B、语义 A/B 各 1227 张。检查解释器、editable 包路径、Git 状态、磁盘、GPU、
   测试、CLI 和 smoke 输入。证据：[同步前审计](../artifacts/server-audit/2026-09-07/before.json)。
   实现提交 `a886936a5119187c8d581bc8d030d4bb62e1479b` 已通过校验 bundle 哈希及
   `--ff-only` 同步到 MGA-current；[同步后审计](../artifacts/server-audit/2026-09-07/after.json)
   记录服务器 89 项测试、核心 Ruff、论文表格一致性、CLI 和 smoke 全部通过，工作区干净。
   CPU 复验汇总从服务器取回后，原始 SHA-256 双端一致：
   `83841cdf9b289e2c17882ac7366fd1bfb5440660a3731e58db9f97fc85d3af9e`。
2. **CPU Parser 复验。** 新增 `--skip-model`，允许不加载 GLiNER 的确定性配置本体检查，
   并支持 class-map 文件。恢复的 1200 条输入在既定配置上 exact match/F1=1.0。
   该数值只说明受控配置覆盖，不是开放语言人工效度；未下载或重跑大型 GPU 后端。
   [复验汇总及输入/配置哈希](../artifacts/revalidation/2026-09-07/configured-parser-cpu/summary.json)。
3. **人工统计工具。** 加入严格输入对齐、缺失与 unverifiable 分离、共同有效样本上的
   AUC/BAcc/FSR、Spearman/Kendall、场景内排序、scene paired bootstrap，以及可选
   仲裁前 nominal Krippendorff α。不会填人工表、推测共识或在测试集选阈值。
   [接入协议](heldout-human-analysis-protocol-2026-09-07.zh-CN.md)。
4. **双语实验章节合并。** 主结果、外部事实基线、参考指标、ROI/Parser/感知消融、
   pilot 与待完成的 held-out 设计已合并。
   [中文](../paper/sections/experiments.zh-CN.v2.md)、[英文](../paper/sections/experiments.en.v2.md)。
   表格由 `scripts/build_paper_experiments.py` 从本地 JSON 生成，附来源链接与
   [数值及规范化 JSON 哈希索引](../artifacts/paper/experiments-v2-source-ledger.json)。
   哈希使用排序键的紧凑 UTF-8 JSON，避免 Windows/Linux 换行差异；它不是源文件原始字节哈希。
5. **验收门槛。** 本地完整测试 89 项通过，核心与本次四个入口 Ruff 通过，
   章节生成器 `--check` 和 `git diff --check` 通过。CI 原先的全仓 Ruff 调整为
   核心加这四个入口，并增加章节源表检查；这不代表历史一次性脚本已全部清理。
   新测试覆盖统计边界和不依赖模型的 Parser 实际命令入口。

## 校正与尚未消除的来源问题

- 旧交接中的 Predicted CD ROI AUC/BAcc 已由 0.689/0.710 更正为 0.693/0.713，
  按 [Hybrid ROI 权威汇总](../artifacts/ablations/predicted-roi-calibration-secondcc-200-v1/hybrid_calibration_summary.json)
  取三位小数。没有修改实验 JSON 或评分公式。
- [早期最小错误汇总](../artifacts/ablations/minimal-error-decomposition-secondcc-200-v1/summary.json)
  的 input_sha256 为 `01a53327ce137ad74b7499c9d6379b7b99dd57b100930c291cada7beab37bc19`；
  当前恢复文件为 `cde0a928ca7c8c522c82b7f5a07b3f9a7bc4e4a7b4a135488af5c4b8ba0d7d87`。
  当前文件匹配恢复记录，但不能因此宣称字节级复现早期实验。差异原因待原始输入备份核对，
  不推测为路径变化，也不覆盖旧数值。
- 在审计列明的 `mga-artifacts` 与 `caption-bench-20260808` 范围内未找到指定的真实模型
  逐条输出、统一 manifest/Claims 和 availability 的 per_subset.jsonl。此结论不覆盖
  用户其他磁盘或备份。紧凑汇总足够支撑归档表格，不足以补算新的逐样本配对统计。
- GitHub Draft PR #1 查询到的 head 为 `7b48834d42d19461866157e25a3d8f36c4f9ce75`，
  未包含本地恢复提交 `68f6335`。冻结提交的 workflow 查询未返回运行记录。
  本轮未公开推送，因此不能把旧 CI 当作本轮验证。

## 后续清单

| 优先级 | 工作 | 所需条件 / 验收结果 |
| --- | --- | --- |
| P0 | 明确正式人工评价单元、候选数与分配 | 用户当前计划约 200 样本、约五人；确认是影像对还是描述，冻结协议与主要比较 |
| P0 | 找回真实候选、Claims 和逐条基线分数 | 先查轻量 JSONL 备份及哈希；缺失时再确定最小重算范围 |
| P0 | 场景去重、与 pilot/dev 隔离、盲化导出 | 单独保存原始票与仲裁；保留描述字节哈希 |
| P0 | 完成 held-out 标注并运行效度统计 | 输出共同支持集、有效 n、配对 CI、评审一致性；不能用旧 pilot 替代 |
| P1 | Oracle Claim 与自动 Parser 对照 | 需要独立人工 Claim；固定视觉证据，分离解析和验证误差 |
| P1 | 受控扰动人工有效性抽检 | 尤其 added hallucination、location、omission；明确错误标签来源 |
| P1 | 补充参考指标后的增量效度 | 有独立标签后预先定义 dev/test 比较；不能由低指标相关性直接推出互补价值 |
| P1 | 核对最小错误历史输入哈希 | 找回原始输入或逐条结果，解释版本差异后才做新的配对重算 |
| P1 | 发布分支并检查远端 CI | 需要明确公开推送授权；只发布代码、文稿及脱敏紧凑汇总 |
| P2 | 确定会议、压缩主文与补充材料 | 依据独立人工效度、真实语言 Parser 误差和增量价值决定；当前不承诺会议级别 |

本轮完成可用输入支持的代码、CPU 复验和章节整理。输入依赖的工作保留在清单中，
没有用模拟人工结果或新下载的大模型替代。服务器保持运行，关机须由用户另行指示。
