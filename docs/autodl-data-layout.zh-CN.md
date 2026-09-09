# AutoDL 数据整理与路径映射记录

## Grounding DINO 模型位置

项目使用 Hugging Face 缓存格式保存 `IDEA-Research/grounding-dino-tiny`，
不是将权重直接放在 MGA 仓库中。

模型快照目录：

```text
/root/autodl-tmp/mga-artifacts/hf-cache/hub/
  models--IDEA-Research--grounding-dino-tiny/
  snapshots/a2bb814dd30d776dcf7e30523b00659f4f141c71/
```

实际权重 blob 约 689 MB，位于：

```text
/root/autodl-tmp/mga-artifacts/hf-cache/hub/
  models--IDEA-Research--grounding-dino-tiny/
  blobs/1a2412ef99bd74bcd3c2a246fa1e48581f8889a1300c9051974741314fc042f3
```

Transformers 通过快照中的符号链接访问 blob，因此不要单独移动或重命名
blob 文件。已缓存模型可使用 `HF_HUB_OFFLINE=1` 离线加载。

## 原始上传文件

```text
/root/autodl-tmp/datasets/LEVIR-MCI-dataset.zip
/root/autodl-tmp/datasets/MGA_segearth.jsonl
/root/autodl-tmp/datasets/change_agent.zip
```

原始文件均被保留，没有移动或覆盖。

盘点结果：

- LEVIR-MCI test：1,929 对 A/B 图像，同时有 `label` 和 `label_rgb`；
- `MGA_segearth.jsonl`：1,000 条，主键字段实际为 `id`；
- Change-Agent：1,000 个 `test_*.txt` 和 100 个 `whucd_*.txt`；
- JSONL 的 1,000 个 LEVIR id、图像 stem 和 `test_*.txt` 完全一一对应；
- 当前上传内容不含 WHU-CD 图像，因此 100 个 WHU 文本只能单独索引。

## 整理后目录

```text
/root/autodl-tmp/datasets/organized/mga_levir_mci_1000/
  images/
    A/                         # 1,000 张前时相图像
    B/                         # 1,000 张后时相图像
  masks/
    source_label/              # 原始灰度 RGB 标签
    source_label_rgb/          # 原始彩色标签
    class_id/                  # MGA 使用的单通道 0/1/2 标签
  results/change_agent/
    levir/                     # 1,000 个 LEVIR Change-Agent 文本
    whu/                       # 100 个尚无图像映射的 WHU 文本
  manifests/
  reports/alignment_report.json
  README.md
```

整理后目录约 301 MB，只提取了 JSONL 实际引用的 1,000 个 test 样本。

## 掩膜转换

LEVIR-MCI 的源 `label` 文件虽然颜色是灰度，但文件模式为 RGB，不能直接交给
当前 MGA 的 `load_label_mask`。整理脚本生成了单通道 `L` 模式 class-id 掩膜：

| 源像素值 | class id | 含义 |
| --- | --- | --- |
| 0 | 0 | 背景/无变化 |
| 128 | 1 | 道路变化 |
| 255 | 2 | 建筑物变化 |

manifest 的 `change_mask` 均指向 `masks/class_id/*.png`。未设置
`metadata.mask_labels` 时，MGA 将 1 和 2 都视为变化区域。

## 主要映射文件

### `path_mapping.jsonl`

1,000 行，每行对应一个场景，记录：

- 规范 `sample_id`；
- 图像 stem；
- A/B 图像绝对路径；
- class-id 掩膜路径；
- 两种源掩膜路径；
- Change-Agent 文本路径；
- 对应的 ZIP 内部 member 名称。

路径：

```text
/root/autodl-tmp/datasets/organized/mga_levir_mci_1000/
  manifests/path_mapping.jsonl
```

### `feedback_aligned.jsonl`

1,000 行，保留原始 Draft、refined、feedback、GT 和裁判结果，同时将原 Windows
A/B 路径替换为服务器绝对路径。

### `all_models_manifest.jsonl`

3,000 行，即 1,000 场景 × Draft、Guided、Change-Agent 三种模型。已经通过：

```bash
mga validate --manifest \
  /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/manifests/all_models_manifest.jsonl
```

该 manifest 尚未包含原子 claims，完整评分前必须先运行 `mga parse`。

### `whu_change_agent_index.jsonl`

100 行，保存 WHU-CD Change-Agent 文本及文件路径，并将图像映射状态标记为
`unavailable_in_current_upload`。在 WHU A/B 图像和变化掩膜上传之前，不应将
这些文本混入 LEVIR manifest。

## 已准备的小批量 manifest

```text
manifests/smoke_first10x3_manifest.jsonl
manifests/smoke_10x3_manifest.jsonl
manifests/smoke_10x3_claims_heuristic.jsonl
manifests/smoke_1x3_claims_heuristic.jsonl
```

- `smoke_first10x3_manifest.jsonl`：数据顺序中的前 10 个场景，用于复现解析边界；
- `smoke_10x3_manifest.jsonl`：筛选出的 10 个三种描述均可被启发式 parser 解析的场景；
- `smoke_10x3_claims_heuristic.jsonl`：30 行，已生成启发式 claims 并通过路径校验；
- `smoke_1x3_claims_heuristic.jsonl`：第一个场景的三模型记录，用于最小 GPU 测试。

直接运行 10 场景评分：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA-current

HF_HUB_OFFLINE=1 mga score \
  --manifest /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/manifests/smoke_10x3_claims_heuristic.jsonl \
  --output /root/autodl-tmp/mga-artifacts/scores/levir_smoke_10x3_v2.jsonl \
  --method v2 \
  --grounder hf-dino \
  --device cuda \
  --cache-dir /root/autodl-tmp/mga-artifacts/grounding-cache
```

## 当前验证结论

- 3,000 行全量 manifest 的路径校验通过；
- A、B、三类掩膜和 LEVIR Change-Agent 各 1,000 个文件；
- WHU Change-Agent 独立保存 100 个文件；
- class-id 掩膜抽检通过，例如 `test_000004.png` 同时包含 0、1、2；
- 已对 `test_000004` 的 Draft、Guided、Change-Agent 执行真实 GPU 评分并输出 3 行结果。

该真实样例中，通用 Grounding DINO tiny 对俯视遥感图像中的 `road`、`tree`、
`vegetation` 未检出目标，三条记录均为 `unverifiable`。这说明路径和推理链路已经
打通，但后续需要评估遥感领域的 prompt、阈值、模型替换或微调，不能把当前的
0 分解释为数据映射失败。

## 可复用整理脚本

本次使用：

```text
scripts/organize_autodl_data.py
```

脚本采用 staging 目录并拒绝覆盖已有输出，保留原始 ZIP，可用于重新构建映射或
审计整理规则。
