# SegEarth-OV-3 AutoDL 部署与可视化测试

更新日期：2026-07-18

## 当前结论

SegEarth-OV-3 适合作为 MGA 当前的主要开放词汇分割候选，Grounding DINO 保留为检测对照和问题诊断工具。

原因如下：

- SegEarth-OV-3 面向遥感图像，官方流程覆盖建筑提取、道路提取、LEVIR-CD 和 WHU-CD。
- 模型直接输出像素级区域，避免 Grounding DINO 框栅格化后大面积覆盖整图的问题。
- RTX 4090 实测峰值显存约 6.19 GiB，能够继续做小批量和阈值消融。
- 首个 LEVIR-MCI 样例的 A/B 掩膜 XOR 结果达到 road IoU 0.621、building IoU 0.683。

上述精度仅来自 `levir-cc_test_000004` 一个样例，不能视为数据集平均结果。

## 服务器部署位置

```text
官方仓库: /root/autodl-tmp/third_party/SegEarth-OV-3
独立环境: /root/autodl-tmp/conda-envs/segearth-ov3
SAM 3 权重: /root/autodl-tmp/third_party/SegEarth-OV-3/weights/sam3/sam3.pt
MGA 项目: /root/autodl-tmp/MGA
输出根目录: /root/autodl-tmp/mga-artifacts/segearth-ov3
```

权重信息：

```text
大小: 3.3 GB
SHA-256: 9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e
来源: https://www.modelscope.cn/models/facebook/sam3
```

环境中的关键版本：

```text
Python 3.12.13
PyTorch 2.10.0+cu128
torchvision 0.25.0+cu128
mmcv-lite 2.2.0
mmengine 0.10.7
mmsegmentation 1.2.2
```

该环境与原 MGA 环境隔离，避免 PyTorch、Transformers、MMCV 和 MMSegmentation 发生依赖冲突。

## 激活环境

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate /root/autodl-tmp/conda-envs/segearth-ov3
cd /root/autodl-tmp/MGA
```

也可以不激活，直接使用固定 Python 路径：

```bash
/root/autodl-tmp/conda-envs/segearth-ov3/bin/python --version
```

## 跑一张图并输出掩膜可视化

```bash
python scripts/run_segearth_ov3.py \
  --image /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/images/B/test_000004.png \
  --entities building road tree \
  --output-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/manual-test
```

每个实体会输出：

- `{image}__{entity}.png`：0/255 二值掩膜；
- `{image}__{entity}__overlay.png`：掩膜与原图的半透明叠加；
- `{image}__combined_overlay.png`：多个实体的彩色合成图；
- `{image}__report.json`：提示词、presence score、实例数、掩膜面积、耗时和峰值显存。

默认颜色为 building 红色、road 蓝色、tree/vegetation 绿色。

## 输出 Grounding DINO 锚框图

先切回 MGA 环境：

```bash
conda activate /root/autodl-tmp/conda-envs/mga
cd /root/autodl-tmp/MGA
```

使用本地模型快照，避免测试时依赖 Hugging Face 网络：

```bash
python scripts/visualize_grounding_dino.py \
  --model /root/autodl-tmp/mga-artifacts/hf-cache/hub/models--IDEA-Research--grounding-dino-tiny/snapshots/a2bb814dd30d776dcf7e30523b00659f4f141c71 \
  --images \
    /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/images/A/test_000004.png \
    /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/images/B/test_000004.png \
  --entities building road tree \
  --query-mode punctuated \
  --output-dir /root/autodl-tmp/mga-artifacts/grounding-visualizations/manual-test
```

`--query-mode` 支持：

- `raw`：原始实体词；
- `punctuated`：只补 Grounding DINO 所需句点；
- `synonyms`：句点格式加遥感同义词扩展。

输出包括每个实体的单独锚框图、每张图的多实体合成锚框图，以及完整坐标和置信度 JSON。

## 生成变化误差图

在 A、B 两期 SegEarth 掩膜均生成后执行：

```bash
python scripts/analyze_segearth_temporal_masks.py \
  --pre-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/levir-cc_test_000004/A \
  --post-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/levir-cc_test_000004/B \
  --reference-mask /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/masks/class_id/test_000004.png \
  --reference-image /root/autodl-tmp/datasets/organized/mga_levir_mci_1000/images/B/test_000004.png \
  --image-stem test_000004 \
  --entity-label road=1 building=2 \
  --output-dir /root/autodl-tmp/mga-artifacts/segearth-ov3/levir-cc_test_000004/temporal
```

误差图颜色：绿色为 TP，红色为 FP，蓝色为 FN。当前实现使用 `A_mask XOR B_mask` 作为预测变化区域。

## 当前样例结果

| 实体 | IoU | Precision | Recall | 主要问题 |
|---|---:|---:|---:|---|
| road | 0.621 | 0.650 | 0.932 | 道路周围裸地和支路区域 FP 偏多 |
| building | 0.683 | 0.712 | 0.944 | 屋顶边缘、圆形裸地区域和小物体 FP 偏多 |

Grounding DINO 对 A 期的 building、road、tree 均产生了接近整幅 256×256 的框；B 期虽有局部框，但道路框仍覆盖大面积场景。因此不建议继续把 DINO 框直接栅格化为 MGA 的主要支持掩膜。

## 后续优化顺序

1. 在 10 个场景上同时跑 A/B 掩膜、合成图和 TP/FP/FN 图，统计均值与异常样例。
2. 分别测试原词和同义词，删除 `structure`、`woodland` 等可能过宽的提示词。
3. 对 `confidence_threshold` 和 `logit_threshold` 做小网格搜索，不要只优化单个样例。
4. 增加小连通域过滤、开闭运算和边界平滑，重点压低 FP。
5. 对比官方 `segearthov3_change_detector.py` 的 LEVIR-CD/WHU-CD 变化检测流程与当前简单 XOR。
6. 通过验证后，再把 SegEarth-OV-3 注册为 MGA 默认 GPU grounder；验证前保留显式后端选择。

## 注意事项

- SegEarth-OV-3 仓库本身未提供独立 `LICENSE` 文件；内嵌 SAM 3 代码和权重受 SAM License 约束。论文研究使用前应保留来源和引用，公开发布或商业使用前需再次核对许可。
- Hugging Face 的 `facebook/sam3` 需要登录并接受访问条款；当前部署使用 SegEarth 官方 README 同时提供的 ModelScope 镜像。
- 不要把 Hugging Face Token、SSH 私钥或密码写入项目文件。若以后需要 Hugging Face，直接在服务器交互执行 `hf auth login`。

## 官方资料

- SegEarth-OV-3 仓库：https://github.com/earth-insights/SegEarth-OV-3
- SegEarth-OV-3 论文：https://arxiv.org/abs/2512.08730
- SAM 3 仓库：https://github.com/facebookresearch/sam3
- SAM 3 权重：https://huggingface.co/facebook/sam3
