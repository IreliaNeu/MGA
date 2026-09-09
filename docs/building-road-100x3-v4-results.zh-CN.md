# Building/Road × SegEarth-OV-3 × MGA v4 结果归档

## 测试范围

- 原始数据：LEVIR-MCI 1000 个双时相场景、3000 条 Caption。
- 一致性审计：检查三模型对应关系、A/B/Mask 文件名、路径、尺寸、类别值和类别映射。
- 合格候选：521 个场景同时具有建筑/道路真实变化，并且至少一个模型 Caption 提到可评价变化主体。
- 最终批量：固定随机种子选取 100 个场景，每个场景包含 Draft、Guided、Change-Agent，共 300 条 Caption。
- 评价实体：仅 `building` 和 `road`。
- 真实标签：`road=1`、`building=2`，按 claim 类别分别评分。

## Parser v4

本轮 Parser 已完成以下调整：

1. `house / villa / residential building / structure / residential area` 统一解析为 `building`。
2. `road / paved road / street / roadway` 统一解析为 `road`。
3. tree、vegetation、water 等无真实类别掩膜的实体不再生成 MGA claim。
4. 变化类型按局部从句和最近谓词绑定，避免把一个变化谓词传播给整句实体。
5. `near/along/around/right side of/both sides of road` 中的 road 解析为 context。
6. 显式出现 `a road is built` 时仍保留 changed road，并与后续 context road 分开。
7. `same as before / remains the same / no difference` 解析为 no-change。

SegEarth 的建筑提示词保持为 `building / house / residential building / villa`，没有重新加入过宽的 `structure`；结构类词只用于文本归一化。

## 最终 MGA v2 结果

| 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---:|---:|---:|---:|---:|
| Draft | 0.561 | 0.856 | 0.859 | **0.681** | 0.392 |
| Guided | 0.562 | 0.848 | 0.847 | **0.673** | 0.418 |
| Change-Agent | 0.548 | 0.804 | 0.884 | **0.657** | 0.375 |

本轮总耗时 119.55 秒，峰值显存 5408.5 MiB。100 个场景全部完成，没有 OOM 或推理中断。

三个模型的 Overall 差距较小，目前只能作为工程基线。正式比较时应在更大的固定样本集上报告 bootstrap 置信区间，并对 Parser 与阈值版本进行锁定。

## 分实体结果

| 实体 | Claims | Faithfulness | Spatial | Temporal | Confidence | Supported | Contradicted | Unverifiable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| building | 254 | 0.635 | 0.470 | 0.940 | 0.888 | 71 | 36 | 147 |
| road | 187 | 0.755 | 0.468 | 0.556 | 0.957 | 126 | 41 | 20 |

Parser v4 将“道路作为空间参照”的 22 条 Caption 正确改为 context。与 v3 相比，road 的 contradicted 从 57 降到 41，supported 从 106 增加到 126。

## 掩膜健康度

| 实体 | A/B 图像数 | 平均面积占比 | 空掩膜 | 近整图掩膜 |
|---|---:|---:|---:|---:|
| building | 200 | 0.126 | 59 | 0 |
| road | 200 | 0.207 | 13 | 7 |

主要问题已经从 tree/vegetation 过分割转为：

1. building 空掩膜比例为 29.5%，是 building unverifiable 较高的直接原因。
2. road 有 7 张近整图掩膜，需要检查 `paved road` 是否在裸地、停车场或硬化地面上过分割。
3. `house` 在 building 查询中胜出 132/200 次，`building` 胜出 61/200 次，`villa` 胜出 7/200 次。
4. `paved road` 在 road 查询中胜出 146/200 次，显著高于原始 `road` 的 54/200 次。

## 后续优化方向

### P0：building 阈值消融

在固定 100 场景上测试 confidence/logit 阈值组合，优先降低 59 张空 building 掩膜，同时监控误分割面积。建议先测试：

```text
confidence: 0.05, 0.10, 0.20
logit:      0.05, 0.10, 0.20
```

### P0：road 提示词消融

分别比较：

```text
road
paved road
road + paved road
```

重点统计近整图掩膜、Spatial、Temporal 和 contradicted 数量，判断 `paved road` 的收益是否大于过分割风险。

### P1：参考掩膜语义抽查

部分图像中视觉上存在新增道路，但参考掩膜仅标注建筑。需要人工抽查低 Spatial、高 grounding confidence 的 road 样例，区分 Caption 错误、Parser 错误和数据集类别标注不完整。

### P1：固定评测协议

下一轮优化应继续使用同一批 100 个 sample_id，不再重新随机抽样。建议锁定：

- `building_road_100x3_claims_v4.jsonl`；
- Parser 版本 `heuristic-building-road-v4`；
- 真实标签 `road=1 / building=2`；
- 每次只改变一个提示词或阈值因素。

## 文件位置与本地保存策略

服务器完整结果：

```text
/root/autodl-tmp/mga-artifacts/segearth-ov3/building-road-100x3-v4
```

服务器最终 Manifest：

```text
/root/autodl-tmp/datasets/organized/mga_levir_mci_1000/manifests/building_road_100x3_claims_v4.jsonl
```

本地只保留以下汇总文件：

```text
artifacts/segearth-ov3/building-road-100x3-v4/
├── batch_overview_contact_sheet.png
├── report.zh-CN.md
├── summary.json
└── audit-summary.json
```

逐 Caption/Claim JSONL、CSV、逐场景掩膜和叠加图只保存在 AutoDL，不再同步到本地。
