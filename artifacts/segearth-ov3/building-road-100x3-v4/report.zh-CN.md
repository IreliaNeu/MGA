# SegEarth-OV-3 小批量 MGA 流程报告

- 场景数：100
- Caption 数：300
- 总耗时：119.55 秒
- 峰值显存：5408.5 MiB
- 后端：`segearth-ov3-native:sam3.pt:confidence=0.1:logit=0.1:expansion=remote-sensing`
- 整批联合可视化：[batch_overview_contact_sheet.png](batch_overview_contact_sheet.png)

## 分模型 MGA v2 均值

| 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |
|---|---:|---:|---:|---:|---:|
| Change-Agent | 0.548 | 0.804 | 0.884 | 0.657 | 0.375 |
| Draft | 0.561 | 0.856 | 0.859 | 0.681 | 0.392 |
| Guided | 0.562 | 0.848 | 0.847 | 0.673 | 0.418 |

## 分实体诊断

| 实体 | Claims | Faithfulness | Spatial | Temporal | Confidence | 状态 |
|---|---:|---:|---:|---:|---:|---|
| building | 254 | 0.635 | 0.470 | 0.940 | 0.888 | contradicted=36, supported=71, unverifiable=147 |
| road | 187 | 0.755 | 0.468 | 0.556 | 0.957 | contradicted=41, supported=126, unverifiable=20 |
| scene | 20 | 0.000 | 0.000 | - | 1.000 | contradicted=20 |

## 场景 × 模型 Overall

| 场景 | Draft | Guided | Change-Agent |
|---|---:|---:|---:|
| levir-cc_test_000004 | 0.936 | 0.936 | 0.936 |
| levir-cc_test_000018 | 0.865 | 0.865 | 0.865 |
| levir-cc_test_000019 | 0.841 | 0.841 | 0.841 |
| levir-cc_test_000048 | 0.891 | 0.891 | 0.891 |
| levir-cc_test_000049 | 0.673 | 0.000 | 0.673 |
| levir-cc_test_000064 | 0.812 | 0.812 | 0.812 |
| levir-cc_test_000068 | 0.837 | 0.837 | 0.837 |
| levir-cc_test_000096 | 0.669 | 0.669 | 0.000 |
| levir-cc_test_000101 | 0.861 | 0.861 | 0.861 |
| levir-cc_test_000124 | 0.000 | 0.206 | 0.741 |
| levir-cc_test_000133 | 0.765 | 0.765 | 0.765 |
| levir-cc_test_000153 | 0.533 | 0.533 | 0.815 |
| levir-cc_test_000158 | 0.878 | 0.878 | 0.878 |
| levir-cc_test_000172 | 0.761 | 0.761 | 0.761 |
| levir-cc_test_000192 | 0.824 | 0.824 | 0.572 |
| levir-cc_test_000200 | 0.829 | 0.829 | 0.829 |
| levir-cc_test_000205 | 0.760 | 0.760 | 0.760 |
| levir-cc_test_000210 | 0.944 | 0.944 | 0.944 |
| levir-cc_test_000228 | 0.862 | 0.864 | 0.862 |
| levir-cc_test_000236 | 0.575 | 0.575 | 0.000 |
| levir-cc_test_000241 | 0.896 | 0.896 | 0.896 |
| levir-cc_test_000248 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000276 | 0.777 | 0.777 | 0.777 |
| levir-cc_test_000285 | 0.712 | 0.712 | 0.714 |
| levir-cc_test_000287 | 0.636 | 0.636 | 0.636 |
| levir-cc_test_000298 | 0.538 | 0.825 | 0.825 |
| levir-cc_test_000300 | 0.753 | 0.753 | 0.753 |
| levir-cc_test_000308 | 0.860 | 0.860 | 0.829 |
| levir-cc_test_000314 | 0.848 | 0.848 | 0.822 |
| levir-cc_test_000321 | 0.848 | 0.848 | 0.848 |
| levir-cc_test_000322 | 0.824 | 0.824 | 0.824 |
| levir-cc_test_000331 | 0.874 | 0.874 | 0.874 |
| levir-cc_test_000333 | 0.387 | 0.387 | 0.000 |
| levir-cc_test_000334 | 0.613 | 0.613 | 0.613 |
| levir-cc_test_000345 | 0.852 | 0.852 | 0.852 |
| levir-cc_test_000349 | 0.871 | 0.871 | 0.871 |
| levir-cc_test_000362 | 0.806 | 0.806 | 0.806 |
| levir-cc_test_000363 | 0.928 | 0.928 | 0.928 |
| levir-cc_test_000366 | 0.800 | 0.800 | 0.800 |
| levir-cc_test_000374 | 0.538 | 0.538 | 0.538 |
| levir-cc_test_000376 | 0.744 | 0.744 | 0.744 |
| levir-cc_test_000379 | 0.784 | 0.784 | 0.784 |
| levir-cc_test_000385 | 0.668 | 0.668 | 0.668 |
| levir-cc_test_000389 | 0.770 | 0.770 | 0.770 |
| levir-cc_test_000390 | 0.561 | 0.000 | 0.561 |
| levir-cc_test_000393 | 0.806 | 0.806 | 0.528 |
| levir-cc_test_000395 | 0.791 | 0.791 | 0.791 |
| levir-cc_test_000402 | 0.636 | 0.636 | 0.636 |
| levir-cc_test_000412 | 0.783 | 0.783 | 0.783 |
| levir-cc_test_000413 | 0.000 | 0.000 | 0.703 |
| levir-cc_test_000416 | 0.818 | 0.818 | 0.818 |
| levir-cc_test_000421 | 0.741 | 0.741 | 0.741 |
| levir-cc_test_000436 | 0.811 | 0.811 | 0.348 |
| levir-cc_test_000443 | 0.766 | 0.766 | 0.590 |
| levir-cc_test_000454 | 0.871 | 0.871 | 0.871 |
| levir-cc_test_000459 | 0.841 | 0.841 | 0.841 |
| levir-cc_test_000466 | 0.709 | 0.709 | 0.000 |
| levir-cc_test_000475 | 0.826 | 0.826 | 0.826 |
| levir-cc_test_000487 | 0.567 | 0.567 | 0.567 |
| levir-cc_test_000488 | 0.788 | 0.788 | 0.788 |
| levir-cc_test_000489 | 0.000 | 0.735 | 0.735 |
| levir-cc_test_000500 | 0.634 | 0.634 | 0.634 |
| levir-cc_test_000528 | 0.843 | 0.843 | 0.843 |
| levir-cc_test_000552 | 0.652 | 0.652 | 0.812 |
| levir-cc_test_000558 | 0.769 | 0.769 | 0.769 |
| levir-cc_test_000564 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000613 | 0.694 | 0.694 | 0.694 |
| levir-cc_test_000622 | 0.808 | 0.808 | 0.890 |
| levir-cc_test_000623 | 0.798 | 0.798 | 0.810 |
| levir-cc_test_000647 | 0.872 | 0.872 | 0.732 |
| levir-cc_test_000652 | 0.814 | 0.814 | 0.814 |
| levir-cc_test_000657 | 0.000 | 0.000 | 0.658 |
| levir-cc_test_000665 | 0.495 | 0.495 | 0.739 |
| levir-cc_test_000668 | 0.853 | 0.856 | 0.853 |
| levir-cc_test_000673 | 0.671 | 0.000 | 0.671 |
| levir-cc_test_000706 | 0.783 | 0.783 | 0.783 |
| levir-cc_test_000721 | 0.871 | 0.871 | 0.859 |
| levir-cc_test_000727 | 0.822 | 0.822 | 0.822 |
| levir-cc_test_000730 | 0.537 | 0.537 | 0.537 |
| levir-cc_test_000748 | 0.746 | 0.746 | 0.746 |
| levir-cc_test_000749 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000772 | 0.667 | 0.667 | 0.667 |
| levir-cc_test_000775 | 0.876 | 0.682 | 0.682 |
| levir-cc_test_000792 | 0.553 | 0.553 | 0.000 |
| levir-cc_test_000793 | 0.638 | 0.638 | 0.765 |
| levir-cc_test_000795 | 0.838 | 0.838 | 0.838 |
| levir-cc_test_000796 | 0.642 | 0.642 | 0.642 |
| levir-cc_test_000810 | 0.741 | 0.741 | 0.000 |
| levir-cc_test_000812 | 0.925 | 0.925 | 0.925 |
| levir-cc_test_000825 | 0.828 | 0.828 | 0.828 |
| levir-cc_test_000851 | 0.692 | 0.692 | 0.692 |
| levir-cc_test_000861 | 0.570 | 0.570 | 0.795 |
| levir-cc_test_000879 | 0.790 | 0.790 | 0.641 |
| levir-cc_test_000891 | 0.719 | 0.719 | 0.719 |
| levir-cc_test_000905 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000913 | 0.762 | 0.762 | 0.000 |
| levir-cc_test_000933 | 0.000 | 0.000 | 0.000 |
| levir-cc_test_000943 | 0.559 | 0.559 | 0.000 |
| levir-cc_test_001000 | 0.472 | 0.472 | 0.472 |
| levir-cc_test_001017 | 0.432 | 0.432 | 0.432 |

## 分割掩膜健康度

| 实体 | 图像数 | 平均面积占比 | 空掩膜 | 近整图掩膜 | 平均置信度 |
|---|---:|---:|---:|---:|---:|
| building | 200 | 0.126 | 59 | 0 | 0.598 |
| road | 200 | 0.207 | 13 | 7 | 0.785 |

## Claim 解析覆盖

- Change type 分布：{'add': 327, 'none': 121, 'modify': 12, 'remove': 1}
- 出现 building claim 的场景：93/100
- 出现 house claim 的场景：0/100
- 出现 road claim 的场景：70/100

## 同义词 Presence 胜出次数

| 实体 | Prompt | 胜出次数 | 平均 Presence |
|---|---|---:|---:|
| building | house | 132 | 0.569 |
| building | building | 61 | 0.549 |
| building | villa | 7 | 0.154 |
| road | paved road | 146 | 0.766 |
| road | road | 54 | 0.752 |

## 最低 Faithfulness Claims

| 场景 | 模型 | 实体 | 状态 | Faithfulness | Spatial | Temporal | Confidence |
|---|---|---|---|---:|---:|---:|---:|
| levir-cc_test_000049 | Guided | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000096 | Change-Agent | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000124 | Draft | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000153 | Draft | road | contradicted | 0.000 | 0.000 | 0.000 | 0.973 |
| levir-cc_test_000153 | Guided | road | contradicted | 0.000 | 0.000 | 0.000 | 0.973 |
| levir-cc_test_000236 | Draft | road | contradicted | 0.000 | 0.000 | 0.000 | 0.918 |
| levir-cc_test_000236 | Guided | road | contradicted | 0.000 | 0.000 | 0.000 | 0.918 |
| levir-cc_test_000236 | Change-Agent | road | contradicted | 0.000 | 0.000 | 0.000 | 0.918 |
| levir-cc_test_000248 | Draft | building | contradicted | 0.000 | 0.000 | 0.000 | 0.293 |
| levir-cc_test_000248 | Guided | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000248 | Change-Agent | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000298 | Draft | road | contradicted | 0.000 | 0.000 | 0.000 | 0.965 |
| levir-cc_test_000333 | Change-Agent | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000390 | Guided | scene | contradicted | 0.000 | 0.000 | - | 1.000 |
| levir-cc_test_000393 | Change-Agent | road | contradicted | 0.000 | 0.000 | 0.000 | 0.984 |
