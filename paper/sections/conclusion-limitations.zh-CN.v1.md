# 5 结论与局限

> 文档状态：中文结论与局限 v1。  
> 写作原则：只总结当前证据能够直接支持的结果；多模型真实输出、Predicted-ROI、ALOHa-local、FMScore-Qwen与Grounding DINO Base/Tiny均已完成，最终人工效度完成后再增强措辞。

## 5.1 结论

本文研究开放式遥感变化语言的事实评价问题。与衡量候选文本和有限参考句相似程度的传统指标不同，MGA将候选描述分解为原子变化Claim，并直接检查实体、变化方向和局部转换关系能否在双时相影像中获得一致证据。由此，评价结果不再只是一个难以解释的整体分数，而是由Spatial、Temporal、Fact Coverage和Verifiability组成的诊断向量。

MGA-Hybrid是本文的主要实现。其核心不是用开放分割替代所有标注，而是对已有类别使用更可靠的语义证据，对标签外实体回退到开放词汇证据，并在证据不足时允许弃权。标注可用性实验表明，随着可靠语义证据逐步增加，Hybrid的事实判别能力和可评分覆盖持续提高，不可验证率相应下降；四路证据对照进一步说明，简单GT查找容易忽略局部source-to-target关系，纯开放词汇证据则受到定位噪声限制。

现有人工pilot为分量式设计提供了初步效度证据。MaskLabelOnly在标签范围内仍是强空间基线，而Temporal是当前与人工事实判断最一致的视觉分量。这一结果说明，MGA的主要价值不在于用一个复杂Overall取代传统分数，而在于把“实体是否出现”“变化方向是否正确”“事实是否遗漏”和“当前证据是否充分”分开报告，使评价结果能够定位生成描述的具体事实错误。

事实保持改写实验进一步说明了图像证据评价与参考文本匹配的互补性。当规范化Claim保持不变时，MGA复用相同双时相证据并保持一致诊断，而传统文本指标仍因词汇和句法变化而下降。因此，MGA不主张删除BLEU、CIDEr或语义文本指标，而是为语言质量之外补充一个独立的图像事实维度。

## 5.2 当前局限

**真实输出上的人工外部效度仍需扩大。** RSICCformer和Chg2Cap已各生成1000条对齐输出，并在固定100场景上完成MGA pilot，说明同一Claim—Evidence接口可稳定处理独立模型家族。但该子集没有逐描述人工正确性标签，LEVIR-MCI人工实验也仍属于50场景pilot。完整投稿仍需在新的盲化人工测试集上比较MGA与传统、图文和事实评价基线。

**无测试GT的开放证据仍依赖领域匹配。** Predicted-CD、RGB差分和No-ROI对照已经量化相对Oracle GT-ROI的差距：跨域ChangeFormer在SECOND上的ROI IoU很低，而域内Change-Agent MCI在LEVIR-MCI上更可靠。这说明无测试GT路线可行但并非无条件稳健；MGA应被描述为支持预测ROI扩展的部分标注/开放证据框架，而不是在任意领域均可靠的完全无标注指标。

**Parser的开放语言泛化尚未充分验证。** 配置化领域词表在受控surface-form上表现稳定，但真实模型输出包含否定、共指、类别歧义和本体外实体。后续将采用规则优先、LLM回退和显式Unknown的级联Parser，并通过独立人工Claim标注评估其精确率、召回率和误差传播。

**单一Overall尚未获得可靠校准。** 人工pilot中Hybrid Overall未优于MaskLabelOnly，而Temporal单项更具判别力。因此，本文优先报告分量向量；只有在独立development数据上完成权重和阈值校准后，Overall才可作为补充排序结果。

## 5.3 后续方向

后续工作将优先完成两项闭环：第一，冻结当前五模型统一评价、强事实基线和七类错误分解的代码与配置；第二，建立按Claim维度标注的独立人工效度集，检验传统指标、ALOHa-local、FMScore-Qwen及MGA各分量与人类实体、方向、位置、幻觉和完整性判断的一致性。Oracle GT-ROI、Predicted-CD ROI、特征差分ROI和No-ROI对照已完成，后续重点是报告其适用边界，而不是继续扩张ROI模型数量。

在这些基础上，MGA可以进一步扩展到变化问答、更丰富的地物类别和一般双时相视觉语言评价。但这些扩展不会改变本文的核心结论：可靠的变化语言评价需要核验文本声明与双时相图像证据之间的关系，而不能只衡量候选文本是否复述了有限参考答案。

## 5.4 Claim—Evidence 自审

- Claim：MGA能够诊断双时相事实错误。  
  Evidence：七类各200条的最小错误分解、关系证据对照和标注可用性曲线。  
  Status：supported in controlled settings；真实输出人工效度待补。

- Claim：Hybrid优于纯GT或纯OV。  
  Evidence：闭集和隐藏类别对照。  
  Status：supported for the reported controlled benchmark；真实多模型人工效度待补。

- Claim：MGA对表达变化更稳健。  
  Evidence：50条强改写中36条通过Claim等价门控；被接受样本的MGA状态一致率为1.0，传统文本分数下降。  
  Status：supported only under exact canonical Claim equivalence；不能推广到任意改写。

- Claim：MGA无需测试GT。  
  Evidence：No-ROI、RGB差分和Predicted-CD ROI已完成；测试Neutral AUC分别为0.748、0.720和0.689，预测ROI未优于No-ROI。  
  Status：部分支持“可运行”，不支持“在任意领域可靠”。

- Claim：MGA适用于开放变化QA。  
  Evidence：受控接口实验成立，Qwen自由回答失败。  
  Status：interface-level only。

## 5.5 投稿前结论段更新占位

`[已完成：多模型统一评价与自动基线]`

> 在1000个LEVIR-MCI对齐场景的5000条真实输出上，MGA-Hybrid已完成统一评分；其Overall从Change-Agent的0.896到Refined的0.736。该数值只表示当前证据流水线下的支持度，不作为模型准确率排名。ALOHa-local、FMScore-Qwen和场景级bootstrap对照也已完成；MGA显著优于ALOHa，但与FMScore-Qwen的总体AUC差异不显著。

`[待补：独立人工效度]`

> 在独立盲化人工测试中，Temporal、Spatial和Fact Coverage与对应人工维度的相关性分别为`TBD/TBD/TBD`，评审一致性为`TBD`。

`[已完成：Predicted-ROI]`

> 在group-disjoint测试集上，No-ROI、RGB特征差分ROI、Predicted-CD ROI和Oracle GT-ROI的Neutral AUC分别为0.748、0.720、0.689和0.739，Coverage均为0.968；对应FSR为0.309、0.289、0.258和0.175。预测ROI没有提高总体AUC，Oracle ROI的主要收益是降低错误支持率。
