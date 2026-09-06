# SegEarth-OV-3 小批量 MGA 流程报告

- 场景数：10
- Caption 数：30
- 总耗时：37.78 秒
- 峰值显存：5410.5 MiB
- 后端：`segearth-ov3-native:sam3.pt:confidence=0.1:logit=0.1:expansion=remote-sensing`
- 整批联合可视化：[batch_overview_contact_sheet.png](batch_overview_contact_sheet.png)

## 分模型 MGA v2 均值

| 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---:|---:|---:|---:|---:|
| Change-Agent | 0.361 | 0.700 | 0.740 | 0.499 | 0.583 |
| Draft | 0.532 | 0.889 | 0.796 | 0.674 | 0.400 |
| Guided | 0.532 | 0.889 | 0.796 | 0.674 | 0.400 |

## 分实体诊断

| 实体 | Claims | Faithfulness | Spatial | Temporal | Confidence | 状态 |
|---|---:|---:|---:|---:|---:|---|
| building | 7 | 0.615 | 0.407 | 1.000 | 0.921 | contradicted=2, supported=2, unverifiable=3 |
| house | 16 | 0.613 | 0.455 | 1.000 | 0.602 | contradicted=1, supported=4, unverifiable=11 |
| road | 13 | 0.339 | 0.388 | 0.279 | 0.639 | contradicted=7, supported=2, unverifiable=4 |
| tree | 7 | 0.362 | 0.187 | 0.687 | 0.926 | contradicted=3, unverifiable=4 |
| vegetation | 5 | 0.434 | 0.256 | 0.764 | 0.870 | contradicted=1, unverifiable=4 |

## 场景 × 模型 Overall

| 场景 | Draft | Guided | Change-Agent |
|---|---:|---:|---:|
| levir-cc_test_000004 | 0.807 | 0.807 | 0.734 |
| levir-cc_test_000017 | 0.748 | 0.748 | 0.747 |
| levir-cc_test_000018 | 0.866 | 0.866 | 0.632 |
| levir-cc_test_000019 | 0.658 | 0.658 | 0.580 |
| levir-cc_test_000020 | 0.782 | 0.782 | 0.782 |
| levir-cc_test_000031 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000032 | 0.857 | 0.857 | 0.393 |
| levir-cc_test_000044 | 0.511 | 0.511 | 0.771 |
| levir-cc_test_000045 | 0.665 | 0.665 | 0.348 |
| levir-cc_test_000047 | 0.850 | 0.850 | 0.000 |

## 分割掩膜健康度

| 实体 | 图像数 | 平均面积占比 | 空掩膜 | 近整图掩膜 | 平均置信度 |
|---|---:|---:|---:|---:|---:|
| building | 20 | 0.094 | 7 | 0 | 0.604 |
| house | 14 | 0.110 | 5 | 0 | 0.613 |
| road | 20 | 0.113 | 0 | 0 | 0.680 |
| tree | 20 | 0.593 | 0 | 2 | 0.859 |
| vegetation | 20 | 0.622 | 0 | 5 | 0.859 |

## Claim 解析覆盖

- Change type 分布：{'modify': 8, 'remove': 22, 'add': 16, 'unknown': 2}
- 出现 building claim 的场景：4/10
- 出现 house claim 的场景：7/10
- 出现 road claim 的场景：6/10

## 同义词 Presence 胜出次数

| 实体 | Prompt | 胜出次数 | 平均 Presence |
|---|---|---:|---:|
| building | house | 8 | 0.583 |
| building | structure | 8 | 0.520 |
| building | building | 4 | 0.578 |
| house | house | 6 | 0.591 |
| house | structure | 6 | 0.526 |
| house | building | 2 | 0.584 |
| road | road | 11 | 0.666 |
| road | paved road | 9 | 0.640 |
| tree | trees | 18 | 0.857 |
| tree | vegetation | 2 | 0.688 |
| vegetation | trees | 18 | 0.857 |
| vegetation | vegetation | 2 | 0.688 |

## 最低 Faithfulness Claims

| 场景 | 模型 | 实体 | 状态 | Faithfulness | Spatial | Temporal | Confidence |
|---|---|---|---|---:|---:|---:|---:|
| levir-cc_test_000031 | Draft | tree | contradicted | 0.000 | 0.000 | 0.000 | 0.938 |
| levir-cc_test_000031 | Guided | tree | contradicted | 0.000 | 0.000 | 0.000 | 0.938 |
| levir-cc_test_000031 | Change-Agent | vegetation | contradicted | 0.000 | 0.000 | 0.000 | 0.938 |
| levir-cc_test_000044 | Draft | road | contradicted | 0.000 | 0.000 | 0.000 | 0.992 |
| levir-cc_test_000044 | Guided | road | contradicted | 0.000 | 0.000 | 0.000 | 0.992 |
| levir-cc_test_000047 | Change-Agent | road | contradicted | 0.000 | 0.000 | - | 0.992 |
| levir-cc_test_000045 | Change-Agent | house | contradicted | 0.052 | 0.052 | - | 0.965 |
| levir-cc_test_000019 | Change-Agent | road | contradicted | 0.337 | 0.493 | 0.048 | 0.613 |
| levir-cc_test_000019 | Draft | road | contradicted | 0.349 | 0.492 | 0.082 | 0.949 |
| levir-cc_test_000019 | Guided | road | contradicted | 0.349 | 0.492 | 0.082 | 0.949 |
| levir-cc_test_000032 | Change-Agent | tree | contradicted | 0.352 | 0.002 | 1.000 | 0.828 |
| levir-cc_test_000045 | Draft | building | contradicted | 0.391 | 0.063 | 1.000 | 0.965 |
| levir-cc_test_000045 | Guided | building | contradicted | 0.391 | 0.063 | 1.000 | 0.965 |
| levir-cc_test_000018 | Change-Agent | road | contradicted | 0.435 | 0.630 | 0.074 | 0.369 |
| levir-cc_test_000019 | Change-Agent | vegetation | unverifiable | 0.499 | 0.253 | 0.954 | 0.836 |
