# 3 方法

## 3.1 问题定义与统一输入表示

给定同一区域在两个时相获得的配准遥感影像 \(I^{1}\) 和 \(I^{2}\)，本文研究如何评价一段开放式语言输出 \(y\) 是否忠实描述了由 \(I^{1}\) 到 \(I^{2}\) 的地表变化。对于变化描述任务，\(y\) 直接对应候选 Caption；对于变化问答任务，输入由问题 \(q\) 和候选回答 \(a\) 组成。我们使用轻量输入适配器 \(\mathcal{A}\) 将不同任务统一为声明式文本：

\[
\tilde y =
\begin{cases}
y, & \text{change captioning},\\
\mathcal{A}(q,a), & \text{change question answering}.
\end{cases}
\]

该适配器只补充问题中已经给定的谓词语义。例如，当问题询问“哪类地物新增”时，回答中的实体被还原为 Add 声明；当问题要求概括主要转移时，回答直接作为 source-to-target 声明解析。适配过程不访问图像、不修改视觉证据，也不改变后续评分函数，因此 Caption 和 QA 可以共享同一个验证器。

Parser 将 \(\tilde y\) 分解为原子声明集合

\[
\mathcal{C}(\tilde y)=\{c_i\}_{i=1}^{N}, \qquad
c_i=(e_i,d_i,\ell_i,r_i,\mathbf a_i),
\]

其中 \(e_i\) 表示规范化实体，\(d_i\in\{\mathrm{Add},\mathrm{Remove},\mathrm{Modify},\mathrm{None},\mathrm{Unknown}\}\) 表示变化方向，\(\ell_i\) 表示空间位置，\(r_i\in\{\mathrm{Changed},\mathrm{Context},\mathrm{NoChange}\}\) 表示声明角色，\(\mathbf a_i\) 保存数量和属性等可选约束。MGA 不以单一总分作为唯一输出，而是报告

\[
\mathbf{s}(y)=
\bigl(S_{\mathrm{spa}},S_{\mathrm{temp}},S_{\mathrm{cov}},
S_{\mathrm{ctx}},U\bigr),
\]

分别对应空间支持、时相支持、事实覆盖、上下文支持和不可验证率。加权 Overall 仅作为补充汇总，不承担主要结论。

## 3.2 领域 Claim 解析与语义规范化

开放式变化语言包含同义词、单复数、被动语态和不同的变化谓词。若直接将原始短语提交给视觉定位器，`house`、`residential building` 和 `structure` 可能产生不一致的查询；若只做关键词匹配，又容易把上下文实体误判为变化实体。为此，我们采用“领域词表优先、轻量模型回退”的级联 Parser。

首先，数据集类别名、通用遥感同义词和版本化 surface-form 表被合并为实体本体 \(\Omega\)。每个文本提及 \(m\) 被映射为规范实体

\[
e=\nu(m;\Omega),
\]

例如 `house/houses/residential area` 被归一化为 `building`，`woodland/tree cover` 被归一化为 `tree`。随后，Parser 在局部从句内绑定变化谓词与实体：`converted from \(e_s\) to \(e_t\)` 被拆为 \(\mathrm{Remove}(e_s)\) 和 \(\mathrm{Add}(e_t)\)，而 `near the road` 中的 `road` 被标记为 Context。只有词表未命中的片段才触发轻量实体抽取器，以提高长尾表达召回并限制额外假阳性。

语义丰富改写不参与 MGA 推理本身。实验中，我们仅在改写前后规范 Claim 签名完全一致时，将样本认定为事实保持改写：

\[
\operatorname{Sig}\!\left(\mathcal{C}(y)\right)
=
\operatorname{Sig}\!\left(\mathcal{C}(y')\right).
\]

若实体、方向、位置、数量或属性任一字段发生变化，则该改写被记为 semantic drift，而不是被计入语言不变性结果。

## 3.3 三种证据模式与逐实体 Hybrid 路由

令 \(M^{t}_{e}\in\{0,1\}^{H\times W}\) 表示实体 \(e\) 在时相 \(t\) 的支持掩膜。MGA 使用两种基础证据源。若双时相语义标签 \(L^{t}\) 提供实体类别 \(k(e)\)，则

\[
M^{t,\mathrm{GT}}_{e}(p)
=\mathbb{1}\!\left[L^{t}(p)=k(e)\right].
\]

若实体不在标签体系内，则开放词汇视觉后端 \(\mathcal{G}\) 根据影像和规范化查询生成

\[
M^{t,\mathrm{OV}}_{e}
=\mathcal{G}\!\left(I^{t},q(e)\right),
\]

其中 \(q(e)\) 可包含规范实体及经校准的遥感同义查询。

基于这两类证据，我们定义三个共享验证器的使用模式：

\[
M^{t,\mathrm{MGA\text{-}GT}}_{e}=M^{t,\mathrm{GT}}_{e},
\]

\[
M^{t,\mathrm{MGA\text{-}OV}}_{e}=M^{t,\mathrm{OV}}_{e},
\]

\[
M^{t,\mathrm{MGA\text{-}Hybrid}}_{e}=
\begin{cases}
M^{t,\mathrm{GT}}_{e}, & e\in\Omega_{\mathrm{ann}},\\
M^{t,\mathrm{OV}}_{e}, & e\notin\Omega_{\mathrm{ann}}.
\end{cases}
\]

MGA-GT 表示完整语义证据下的理想上界；MGA-OV 用于压力测试开放视觉后端；MGA-Hybrid 是本文的主要配置，它利用已标注类别的可靠空间证据，同时保留验证标签外实体的能力。该路由以实体为单位，而不是以整条句子为单位，因此同一 Caption 中的 building 可以使用 GT，而 tree 或 water 可以回退到开放词汇掩膜。

需要说明的是，当前受控 MGA-OV 实验仍使用语义变化 ROI 隔离实体 Grounder 的误差，因此它检验的是“纯开放实体证据”，不等同于完全无标注部署。完全无标注版本还需要由影像自身估计变化 ROI。

## 3.4 双时相变化证据构造

单时相实体存在不能证明变化方向。给定同一实体在两个时相的掩膜，MGA 分别构造新增、移除和修改证据：

\[
A_e=M^{2}_{e}\cap\neg\mathcal{D}_{\rho}(M^{1}_{e}),
\]

\[
R_e=M^{1}_{e}\cap\neg\mathcal{D}_{\rho}(M^{2}_{e}),
\]

\[
X_e=M^{1}_{e}\oplus M^{2}_{e},
\]

其中 \(\mathcal{D}_{\rho}\) 是半径为 \(\rho\) 的形态学膨胀，用于容忍双时相配准和分割边界的小幅偏移。对于 source 实体 \(e_s\) 被 target 实体 \(e_t\) 替代的关系声明，我们进一步构造

\[
Q_{s\rightarrow t}
=
\mathcal{D}_{\delta}(R_{e_s})
\cap
\mathcal{D}_{\delta}(A_{e_t})
\cap
L_{\ell},
\]

其中 \(L_{\ell}\) 是由 Claim 位置 \(\ell\) 定义的空间窗口。该交集要求 source-remove 与 target-add 在同一局部变化区域内形成一致关系，而不是只在两幅图中分别找到两个实体。

若提供二值或语义变化标注，则真实变化区域记为

\[
G=\mathbb{1}[L^{1}\neq L^{2}]
\]

或数据集给定的二值变化掩膜。针对带类别语义标签的关系实验，理想转移区域还可写为

\[
G_{s\rightarrow t}
=\mathbb{1}[L^{1}=k(e_s)]
\cap
\mathbb{1}[L^{2}=k(e_t)].
\]

## 3.5 Claim 级验证与分量式评分

### 空间支持

令 \(E_i\) 表示与 Claim \(c_i\) 对应的实体或关系证据，则空间支持采用证据精度：

\[
S^{(i)}_{\mathrm{spa}}
=
\frac{|E_i\cap G_i|}
{|E_i|+\varepsilon}.
\]

该定义回答“被定位为文本证据的区域中，有多少位于真实变化区域”，从而抑制与变化无关的大面积分割。

### 时相支持

对于 Add 和 Remove，时相支持分别衡量目标时相证据在变化 ROI 中的新增性和消失性：

\[
S^{(i)}_{\mathrm{temp,add}}
=
\frac{|A_{e_i}\cap G_i|}
{|M^{2}_{e_i}\cap G_i|+\varepsilon},
\]

\[
S^{(i)}_{\mathrm{temp,remove}}
=
\frac{|R_{e_i}\cap G_i|}
{|M^{1}_{e_i}\cap G_i|+\varepsilon}.
\]

Modify 使用异或差分：

\[
S^{(i)}_{\mathrm{temp,modify}}
=
\frac{|X_{e_i}\cap G_i|}
{|(M^{1}_{e_i}\cup M^{2}_{e_i})\cap G_i|+\varepsilon}.
\]

对于 source-to-target 关系，则使用

\[
S^{(i)}_{\mathrm{rel}}
=
\frac{|Q_{s\rightarrow t}\cap G|}
{|Q_{s\rightarrow t}|+\varepsilon}.
\]

### 事实覆盖与不可验证性

将真实变化掩膜分解为满足最小面积约束的连通分量
\(\{g_j\}_{j=1}^{K}\)。若预测支持并集
\(E=\bigcup_i E_i\) 对分量 \(g_j\) 的重叠率不低于
\(\tau_{\mathrm{cov}}\)，则该事实被覆盖：

\[
S_{\mathrm{cov}}
=
\frac{1}{K}
\sum_{j=1}^{K}
\mathbb{1}
\left[
\frac{|E\cap g_j|}{|g_j|}
\ge \tau_{\mathrm{cov}}
\right].
\]

当视觉后端未能提供超过置信度阈值的目标证据时，MGA 不把检索失败直接解释为文本错误，而将 Claim 标记为 Unverifiable。Caption 级不可验证率为

\[
U=\frac{1}{N}\sum_{i=1}^{N}
\mathbb{1}[z_i=\mathrm{Unverifiable}].
\]

对每个 Claim，若任一可用证据轴不高于反驳阈值
\(\tau_{\mathrm{con}}\)，则状态为 Contradicted；若所有可用轴均不低于支持阈值 \(\tau_{\mathrm{sup}}\)，则为 Supported；其余情况为 Unverifiable。当前实现使用
\(\tau_{\mathrm{con}}=0.25\) 和 \(\tau_{\mathrm{sup}}=0.60\)。该联合判定避免高空间分数掩盖新增/移除方向颠倒。

为便于补充分析，可将可用分量加权为

\[
F_i
=
\frac{
w_s S^{(i)}_{\mathrm{spa}}
+
w_t S^{(i)}_{\mathrm{temp}}
}{
w_s\mathbb{1}[S^{(i)}_{\mathrm{spa}}\text{ available}]
+
w_t\mathbb{1}[S^{(i)}_{\mathrm{temp}}\text{ available}]
},
\]

其中当前实现取 \(w_s=0.65\)、\(w_t=0.35\)。但主实验优先分别报告 Spatial、Temporal、Coverage 和 \(U\)，不将 \(F_i\) 或 Overall 作为唯一质量判断。

## 3.6 统一推理流程与任务适应

完整流程可概括为：

1. Caption 直接输入，或将 QA 对通过 \(\mathcal A(q,a)\) 还原为声明式文本；
2. 通过领域 Parser 和同义词本体生成原子 Claim；
3. 按 MGA-GT、MGA-OV 或 MGA-Hybrid 为每个实体选择双时相证据；
4. 构造 Add、Remove、Modify 和 source-to-target 关系掩膜；
5. 计算 Claim 级空间/时相支持并产生 Supported、Contradicted 或 Unverifiable 状态；
6. 聚合 Coverage、Context Support 与 Unverifiable Rate，输出 Caption/Answer 级诊断。

从变化描述迁移到开放变化问答只增加步骤 1 的输入适配器，步骤 2–6 的证据、公式和阈值均保持不变。由此，新增问答实验检验的是 MGA 的任务接口可迁移性，而不是另一套为 QA 单独设计的评价函数。
