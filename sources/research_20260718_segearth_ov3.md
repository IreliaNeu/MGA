# SegEarth-OV-3 接入调研记录

日期：2026-07-18

## 检索说明

`research-lookup` 首选服务因服务器未配置 `PARALLEL_API_KEY` 和 `OPENROUTER_API_KEY` 而无法执行。本记录改用官方仓库、官方模型页和原始论文进行核查，避免依赖二手文章。

## 核查结论

1. SegEarth-OV-3 是基于 SAM 3 的无训练遥感开放词汇语义分割方案，融合 SAM 3 的 semantic head 与 Transformer instance head，并使用 presence score 过滤不存在的类别。
2. 官方仓库列出的任务包括建筑提取、道路提取、LEVIR-CD、WHU-CD、S2Looking 变化检测，与 MGA 当前数据高度匹配。
3. 论文报告在 20 个分割数据集、3 个变化检测数据集和 1 个三维数据集上进行评估；论文当前为 arXiv 预印本，2026-04-22 更新到 v2。
4. SAM 3 官方当前建议 Python 3.12+、PyTorch 2.7+、CUDA 12.6+；官方示例使用 PyTorch 2.10/cu128。
5. Hugging Face 权重需要登录并接受条款。SegEarth-OV-3 README 同时提供 ModelScope 镜像，本次部署从该镜像取得 `sam3.pt`。
6. SegEarth-OV-3 仓库没有完整依赖锁定，也没有独立 LICENSE 文件；部署应使用独立环境，并单独核对 SAM License。

## 实测补充

- 服务器：NVIDIA RTX 4090 24 GB，驱动 595.71.05。
- 官方遥感样图：模型加载 20.66 秒，3 个实体推理 2.06 秒，峰值显存 6188 MiB。
- LEVIR-MCI `test_000004`：building temporal XOR IoU 0.683，road temporal XOR IoU 0.621。
- Grounding DINO 在同一 A 期样例上对 building、road、tree 均输出接近整图的框，进一步支持把 SegEarth-OV-3 作为像素分割主候选。

## 一手来源

- SegEarth-OV-3 官方仓库：https://github.com/earth-insights/SegEarth-OV-3
- SegEarth-OV-3 论文：https://arxiv.org/abs/2512.08730
- SAM 3 官方仓库：https://github.com/facebookresearch/sam3
- SAM 3 官方模型页：https://huggingface.co/facebook/sam3
- SAM 3 ModelScope 镜像：https://www.modelscope.cn/models/facebook/sam3
- SegEarth-OV CVPR 2025 论文：https://openaccess.thecvf.com/content/CVPR2025/papers/Li_SegEarth-OV_Towards_Training-Free_Open-Vocabulary_Segmentation_for_Remote_Sensing_Images_CVPR_2025_paper.pdf
