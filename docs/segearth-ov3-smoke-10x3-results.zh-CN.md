# SegEarth-OV-3 × MGA 小批量流程测试结果

## 1. 本次测试范围

- 数据：LEVIR-MCI 测试集中的 10 个双时相场景。
- Caption：每个场景包含 Draft、Guided、Change-Agent，共 30 条。
- Claim：启发式解析得到 48 条实体变化声明。
- 分割后端：SegEarth-OV-3 原生 SAM3 checkpoint。
- 推理配置：`confidence=0.1`、`logit=0.1`、`expansion=remote-sensing`。
- 输出：A/B 时相逐实体掩膜、联合实体叠加图、参考变化叠加图、MGA v2 明细与汇总。

服务器结果目录：

```text
/root/autodl-tmp/mga-artifacts/segearth-ov3/smoke-10x3-v1
```

本地镜像目录：

```text
artifacts/segearth-ov3/smoke-10x3-v1
```

## 2. 运行情况

| 指标 | 结果 |
|---|---:|
| 场景数 | 10 |
| Caption 数 | 30 |
| 总耗时 | 37.78 秒 |
| 平均每场景耗时 | 3.78 秒 |
| 峰值显存 | 5410.5 MiB |

模型只加载一次，同一场景的实体统一进行 A/B 两次分割，因此这套实现可以直接扩展到更大的批量。当前 10 场景测试未出现显存溢出或推理中断。

## 3. MGA v2 结果

| Caption 来源 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---:|---:|---:|---:|---:|
| Draft | 0.532 | 0.889 | 0.796 | 0.674 | 0.400 |
| Guided | 0.532 | 0.889 | 0.796 | 0.674 | 0.400 |
| Change-Agent | 0.361 | 0.700 | 0.740 | 0.499 | 0.583 |

Draft 与 Guided 的均值完全相同，是因为这批数据中二者多数文本相同；即使个别文本不同，启发式解析后得到的有效 claims 仍相同。该结果不能直接解释为两种生成方法能力相同。

48 条 claims 的状态分布为：

- supported：8 条；
- contradicted：14 条；
- unverifiable：26 条，占 54.2%。

当前分数应视为“流水线联调基线”，而不是 SegEarth-OV-3 或 Caption 模型的最终性能结论。Unverifiable 比例较高，说明 claim 解析和证据匹配仍是主要瓶颈。

## 4. 分实体表现

| 实体 | Claims | Faithfulness | Spatial | Temporal | Confidence |
|---|---:|---:|---:|---:|---:|
| building | 7 | 0.615 | 0.407 | 1.000 | 0.921 |
| house | 16 | 0.613 | 0.455 | 1.000 | 0.602 |
| road | 13 | 0.339 | 0.388 | 0.279 | 0.639 |
| tree | 7 | 0.362 | 0.187 | 0.687 | 0.926 |
| vegetation | 5 | 0.434 | 0.256 | 0.764 | 0.870 |

结论：

1. building/house 的变化方向判断较稳定，但存在 A 时相空掩膜较多的问题，需要通过阈值扫描确认是真正未检出还是阈值过严。
2. road 的置信度并不低，但 Temporal 只有 0.279。可视化显示道路通常在 A/B 两个时相都被稳定分出，因此将“作为空间参照的道路”误判成变化实体会产生明显低分。
3. tree/vegetation 的置信度很高，但平均掩膜面积分别达到 0.593 和 0.622；其中 vegetation 有 5 张近整图掩膜。这是典型的高置信度过分割，不能只依赖 presence/confidence 选择同义词。

## 5. 同义词映射诊断

- `trees` 在 tree/vegetation 两类共 40 次 A/B 推理中胜出 36 次，导致 tree 与 vegetation 几乎退化为同一宽泛类别。
- `structure` 在 building/house 查询中频繁胜出，但语义范围比目标建筑更宽，可能把非建筑构筑物纳入掩膜。
- `paved road` 在 road 查询中 20 次胜出 9 次，有一定遥感适配价值，可以保留用于后续消融。

建议下一版拆开同义词配置：

```text
building: building, house, residential building, villa
house: house, residential building, villa
road: road, paved road
tree: tree, tree crown, individual tree
vegetation: vegetation, vegetated area, green cover
```

暂时移除 `structure`，并禁止 tree 与 vegetation 相互作为同义词。后续选择提示词时，应同时考虑置信度、面积先验和 A/B 稳定性，而不是只取最高 presence。

## 6. 典型失败样例

### `levir-cc_test_000031`

Caption 描述“树被移除、湖泊出现”，但参考变化掩膜只覆盖一个很小的建筑区域。该场景得到 0 分，主要表现为文本、实体语义和参考掩膜疑似错配。下一批运行前应先做数据一致性审计。

### `levir-cc_test_000044`

Caption 为“房屋出现在道路右侧”。road 只是空间位置参照，却被启发式 parser 解析成 `road:add`，而 A/B 中道路均稳定存在，因此该 claim 得到 0 分。这是关系解析问题，不是道路分割失败。

### `levir-cc_test_000047`

Change-Agent 文本为“a villa is built ... near the road”。当前 parser 没有把 villa 映射为 building，只抽取了作为参照物的 road，并且变化类型为 unknown，导致得分为 0。需要增加 villa/building 映射并进行从句级谓词绑定。

### `levir-cc_test_000018`

Draft 只描述新增房屋，解析与视觉证据一致，Overall 为 0.866；Change-Agent 同时描述 vegetation、house、road，当前 parser 将同一变化谓词错误传播到多个实体，Unverifiable 达到 0.667。该样例说明复杂 Caption 必须按从句解析变化关系。

## 7. 后续优化优先级

### P0：先修 claim parser 和数据一致性

1. 增加 `villa → building/house`、`villas → building/house` 等映射。
2. 采用从句级实体—变化谓词绑定，避免把 `removed` 或 `built` 传播给整句所有实体。
3. 区分“变化主体”和“空间参照实体”，例如 `right of the road`、`near the road` 中的 road 不应自动生成变化 claim。
4. 自动检查 Caption、A/B 图像和参考掩膜是否同一 sample_id，并将 `000031` 一类疑似错配样本隔离。

### P1：收紧 SegEarth 同义词与掩膜后处理

1. 拆分 tree/vegetation 提示词，移除跨类同义词。
2. 对 building/house 移除过宽的 `structure`，增加 `villa` 和 `residential building`。
3. 对置信度阈值和 logit 阈值做小网格扫描，例如 0.1/0.2/0.3。
4. 增加面积异常惩罚、连通域过滤以及边界平滑；近整图掩膜应标为低可靠证据。

### P1：调整 MGA 证据定义

当前 spatial support 使用整张非零参考变化掩膜，没有 building、road 等类别标签。因此“实体分割是否正确”和“实体是否落在任意变化区域”仍被混在一起。建议：

1. 对建筑/道路参考掩膜建立 `mask_labels`，按实体类别计算空间支持。
2. 对 add/remove 分别使用 `B-A` 与 `A-B`，对 modify 使用 XOR/IoU 组合。
3. 将作为位置参照的实体证据单独计分，不参与变化主体的 Temporal 分数。

### P2：扩大验证批量

完成 P0/P1 后再运行 50–100 个场景，比较：

- 原始提示词与收紧提示词；
- 不同置信度/logit 阈值；
- 规则 parser 与从句级 parser；
- SegEarth 证据与 Grounding DINO 锚框证据。

只有当 Unverifiable 明显下降、tree/vegetation 近整图掩膜比例下降后，MGA 均值才适合用于模型之间的正式比较。

## 8. 输出文件

| 文件 | 用途 |
|---|---|
| `batch_overview_contact_sheet.png` | 10 个场景的联合可视化总览 |
| `scenes/*/overview_A_B_reference.png` | 单场景 A/B 多实体分割与参考变化对照 |
| `scenes/*/A_masks`、`B_masks` | 逐实体二值掩膜 |
| `mga_scores.jsonl` | Caption 与 claim 级完整 MGA 结果 |
| `segmentations.jsonl` | 分割查询、置信度、面积比例与文件路径 |
| `summary.json` | 机器可读汇总 |
| `report.zh-CN.md` | 自动生成的批量报告 |
| `caption_scores.csv` | Caption 级平铺结果 |
| `claim_scores.csv` | Claim 级平铺结果 |

## 9. 复现命令

```bash
source /etc/network_turbo
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/segearth-ov3
cd /root/autodl-tmp/MGA

python scripts/run_segearth_mga_batch.py \
  --manifest /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/manifests/smoke_10x3_claims_heuristic.jsonl \
  --output-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/smoke-10x3-v1 \
  --cache-dir /root/autodl-tmp/mga-artifacts/grounding-cache/segearth-ov3-smoke-10x3-v1 \
  --checkpoint /root/autodl-tmp/third_party/SegEarth-OV-3/weights/sam3/sam3.pt

python scripts/summarize_segearth_mga_batch.py \
  --run-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/smoke-10x3-v1
```
