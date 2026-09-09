# 独立人工效度统计接入协议 v1

状态：统计实现已准备，正式人工数据未完成。约 200 条样本、约五名评审为用户当前计划；
影像对/候选描述的单位、评审分配及评分规则仍需在正式标注前确定。本协议不替用户做人工判断。

## 输入与职责

`scripts/analyze_heldout_human_validity.py` 接受**已经对齐的共识标签和自动分数**，
不读取/改写原始 XLSX，不推测多数票规则，不拟合新 Overall，不自动选择测试阈值。
输入应由未来人工表的字段映射导出，原始票与仲裁结果分别保存。所有逐条输入放到
`data/private/` 或服务器持久目录，不加入 Git；只有脱敏紧凑汇总可归档。

每行代表同一候选或 Claim 在一个维度上的共识判断：

```json
{
  "scene_id": "scene-001",
  "item_id": "scene-001/candidate-A",
  "dimension": "direction",
  "split": "test",
  "caption_sha256": "<原始描述UTF-8字节的64位小写SHA-256>",
  "human_status": "rated",
  "human_score": 1,
  "human_binary": 1,
  "scores": {"MGA-Temporal": 0.8, "FMScore-Qwen": 0.7}
}
```

上例仅解释字段，不是人工结果。相同 `item_id` 跨维度必须保留相同影像 ID 和描述哈希。
同一影像不能同时出现在 `dev/test/pilot/training` 的不同 split；导出时必须包含用于排除
旧 pilot/开发场景的完整分组记录或先独立完成排除审计。工具能验证输入内冲突，不能发现
未提供的历史场景泄漏，也不能从单个合并哈希反向验证各原始指标文件；导出者必须逐源校验
`item_id`、描述及其哈希。标点/空格版本不应静默规范化后视为同一候选。

- `human_status`：`rated / unverifiable / not_applicable`。后两者的两个目标均必须为 null。
- `human_score`：按预先固定的规则聚合的数值目标，例如二值票比例或整体事实性等级。
- `human_binary`：明确定义的二值目标 0/1；无二值共识或不拟二值化时用 null。
  工具不会把整体事实性 1–5 分擅自映射为正确/错误。
- `scores`：必须显式列出配置中的全部指标；不可用填 null。空值不默认为 contradiction。
  缺文件/未计算与模型弃权应在上游导出审计中区分；这里统一报告 unavailable 数量，
  不把所有 unavailable 宣称为模型的 unverifiable rate。

## 指标方向与阈值

另提供 JSON，例如：

```json
{
  "MGA-Temporal": {"direction": 1, "threshold": 0.6},
  "FMScore-Qwen": {"direction": 1, "threshold": null}
}
```

这里的 0.6 是字段用法示例，不是新人工测试的预注册决定。direction 为 1 表示越大越好，
-1 表示越小越好；threshold 始终使用原始量纲。null 时不报告该指标 BAcc/FSR。
必须先记录阈值由何种 development 数据选择或采用何种冻结默认值。

## 统计口径

1. 各指标先单独报告有效 n、正负例数和 evaluation coverage，以及条件 AUC、BAcc、FSR、
   Spearman、Kendall τ-b。纯缺失不做中性补值，因为不同基线的原始量纲不统一。
2. 比较使用当前配置中**全部指标共同可用的同一组目标**。若共同集合过小，应按预先定义的
   主要比较分别提供指标配置；不能根据显著性临时选择有利集合。原始条件结果与共同集合结果并列。
3. Paired bootstrap 的重采样单位为 scene，整组保留同场景候选；每个抽样副本获得不同场景索引，
   避免同一场景重复抽中后产生跨副本伪候选对。默认 2,000 次，seed=20260907。
4. Pairwise accuracy 在场景内比较人类有严格先后的候选；人类并列排除，自动并列计 0.5。
   先算每个场景的准确率再宏平均。若分析 Claim 行，此统计代表场景内 Claim 排序，不能标成
   候选描述排序；建议共识输入一次只包含同一种评价单元。
5. 每项差异区间来自同一 bootstrap 抽样，不从两个独立区间相减。记录有效重采样次数；
   缺正类或负类的抽样不产生 AUC/BAcc，单场景不报告场景采样区间。
6. 二值判别与等级相关分别使用各自有定义的目标，保留各自有效 n。FSR 是可评分负例中的误支持率。

## 原始评审一致性

可选 `--votes` 输入同样为 JSONL，字段为 `scene_id / item_id / dimension / caption_sha256 /
rater_id / rating`。rating 为数值、`unverifiable`、`not_applicable` 或 null。
原始票必须来自仲裁前；工具校验候选哈希、场景与重复评审，但无法从标签本身确认是否仲裁前。

当前实现报告 nominal Krippendorff α、至少两票的单元数、票数和全体一致比例。
`unverifiable` 作为独立类别；not_applicable、空白不进入 α。数值等级也按名义类别计算，
不假定等级间距；若正式协议选择 ordinal α，应新增独立实现与验证，不能将现输出改名。

## 运行

```bash
python scripts/analyze_heldout_human_validity.py \
  --input data/private/heldout-v1/aligned_consensus.jsonl \
  --votes data/private/heldout-v1/pre_adjudication_votes.jsonl \
  --metric-specs data/private/heldout-v1/frozen_metric_specs.json \
  --output artifacts/human-eval/heldout-v1/summary.json \
  --split test --replicates 2000 --seed 20260907
```

输出已存在时命令拒绝覆盖。正式统计前仍需确认：场景独立性、候选分配、图像展示顺序、
盲化、缺失/不适用规则、票聚合规则、主要终点、主要比较及多重比较处理。
现有 CPU 单元测试只验证统计行为，不构成人工效度结果。
