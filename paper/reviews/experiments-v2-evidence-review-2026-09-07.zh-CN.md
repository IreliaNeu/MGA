# 实验章节 v2 证据复核

审阅对象：[中文章节](../sections/experiments.zh-CN.v2.md)与
[英文章节](../sections/experiments.en.v2.md)。表格数值逐源绑定于
[证据索引](../../artifacts/paper/experiments-v2-source-ledger.json)。

## 论证顺序

1. 设置与分数口径：先区分真实候选、受控错误、语义证据条件及各自评价覆盖。
2. 类别可用性：解释 Hybrid 为什么需要实体级路由，展示 coverage 与判别质量。
3. 错误分解和外部基线：展示诊断能力，同时保留 FMScore-Qwen 的竞争性。
4. 真实候选和参考指标：展示分布与指标关系，把增量效度作为待人工检验的问题。
5. ROI、Parser 与感知消融：定位系统表现对证据条件的依赖。
6. 人工 pilot 与独立实验：明确旧 pilot 的不同有效 n 和新实验尚无结果。

## 主张—证据复核

| 主张 | 来源 | 判断与边界 |
| --- | --- | --- |
| 可靠语义证据增加时 Hybrid 判别与可评分覆盖提高 | availability curve JSON（章节表 1） | 支持；FSR 非单调，不能改写为所有指标同步改善 |
| 双时相检查诊断不同事实错误 | minimal-error summary（表 3） | 支持受控范围；omission 使用 fact coverage，不能声称纯视觉发现所有遗漏 |
| 相较 ALOHa-local 有 AUC 优势 | external-metric-comparison（表 4） | 配对区间支持；对 FMScore-Qwen 的差异区间跨零 |
| 真实输出存在不同支持度和解析覆盖 | unified summary（表 5） | 支持分布描述；不是生成人工准确率排名 |
| 补充参考文本指标 | alignment + 各参考指标汇总（表 6–7） | 当前提供机制和关联证据；有效增量仍需独立人工标签 |
| Predicted ROI 更好 | hybrid_calibration_summary（表 8） | 只支持本条件下 FSR 变化，不支持总体 AUC 提升 |
| 配置 Parser 的覆盖充分 | parser_report_v3（表 10） | 只支持配置表达集；无真实语言独立 gold，不能称开放语言准确率 |
| 人工效度已验证 | pilot alignment（表 12） | 不成立；pilot 小且 Overall 弱，不同分量 n 不同，held-out 待完成 |

## 五项检查

- 问题聚焦：主线是双时相 Claim—Evidence 诊断，不扩展为通用 QA 或全面指标替代。
- 比较公平：隔离不同 annotation/ROI/abstention 协议，保留适配版本与 Oracle 阈值说明。
- 统计单位：区分场景、描述、Claim；历史汇总不补造显著性，新工具采用 scene bootstrap。
- 可复现性：生成器核验表格及源 JSON 的规范化哈希；原始输入哈希问题单列于最新工作清单。
- 行文强度：先陈述实验发现，限制紧邻对应解释；独立人工部分不填占位数值。

后续需要根据最终人工协议添加主要终点、评审分配与一致性定义，再用真实汇总替换
held-out 待完成段落。现版本仍是完整工作草稿，投稿页数压缩与最终方法章节交叉核对尚未完成。
