# 事实评价与遥感变化描述指标：本轮检索来源

检索日期：2026-08-13。以下仅记录用于本轮复现决策和论文表述的论文主页、官方代码仓库或官方模型页。

## Grounding DINO Base

- 官方 Hugging Face 模型页：<https://huggingface.co/IDEA-Research/grounding-dino-base/tree/main>
- Transformers 官方模型文档：<https://huggingface.co/docs/transformers/model_doc/grounding-dino>
- 用途：确认 `IDEA-Research/grounding-dino-base` 是可直接通过 Transformers 加载的开放词汇检测模型；官方文件页显示 `model.safetensors` 约 933 MB。

## ALOHa

- 论文：Petryk et al., “ALOHa: A New Measure for Hallucination in Captioning Models,” NAACL 2024：<https://aclanthology.org/2024.naacl-short.30/>
- 官方代码：<https://github.com/DavidMChan/aloha>
- 用途：确认 ALOHa 的核心为对象抽取、语义相似度、匈牙利匹配与最小匹配分数。官方示例默认使用 GPT-3.5 对象解析器和 MPNet；仓库也提供本地解析接口。
- 本轮实现边界：使用官方仓库的本地 SpaCy 对象解析器、MPNet 相似度与匹配逻辑；由于 `en_core_web_lg` 下载失败，使用 `en_core_web_sm 3.7.1`。因此记为 **ALOHa local variant**，不声称复现论文的 GPT-3.5 默认配置。

## FMScore

- 论文：Baiocchi et al., “Remote sensing change captioning meets large language and vision models,” ISPRS Journal of Photogrammetry and Remote Sensing, 2026：<https://doi.org/10.1016/j.isprsjprs.2026.06.003>
- 出版页：<https://www.sciencedirect.com/science/article/abs/pii/S0924271626003035>
- 用途：确认 FMScore 使用事实集合和 LLM 判断生成段落是否蕴含各事实，原文实验使用 Vicuna-13B。
- 本轮实现边界：保留 yes/no 事实推断协议，但推理器替换为本地 `Qwen3-VL-2B-Instruct`，固定解码，故论文中必须写作 **FMScore-Qwen protocol adaptation**，不能写成原始 FMScore 的完全复现。

## InfoMetIC

- 论文：Hu et al., “InfoMetIC: An Informative Metric for Reference-free Image Caption Evaluation,” ACL 2023：<https://aclanthology.org/2023.acl-long.178/>
- 官方代码：<https://github.com/HAWLYQ/InfoMetIC>
- 用途：作为已发表参考无关图像描述评价方法的候选强基线。
- 未运行原因：官方仓库要求约 119 GB 的预处理 COCO 特征和约 462 MB 权重，且 README 明确写明基准训练/评价代码尚未发布；本轮数据盘仅余约 6.5 GB。直接将其迁移到双时相遥感场景也不构成可核查的等价复现。

## 遥感变化描述复合指标

- CCExpert 论文：<https://arxiv.org/abs/2411.11360>
- CCExpert 官方代码：<https://github.com/Meize0729/CCExpert>
- 用途：核对遥感变化描述论文的常规生成指标报告习惯。本轮对 Draft/Refined 计算：
  - `S*m = (BLEU-4 + METEOR + ROUGE-L + CIDEr-D) / 4`
  - `SPIDEr = (SPICE + CIDEr-D) / 2`
- 说明：二者仍是参考文本驱动的复合分数，不具备双时相视觉证据验证能力。

