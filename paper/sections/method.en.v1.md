# 3 Method

## 3.1 Problem Formulation and Unified Input Representation

Given two co-registered remote-sensing images \(I^{1}\) and \(I^{2}\) acquired over the same area, we evaluate whether an open-ended language output \(y\) faithfully describes the surface changes from \(I^{1}\) to \(I^{2}\). For change captioning, \(y\) is the candidate caption. For change question answering, the input consists of a question \(q\) and a candidate answer \(a\). A thin adapter \(\mathcal{A}\) maps both tasks to a declarative representation:

\[
\tilde y =
\begin{cases}
y, & \text{change captioning},\\
\mathcal{A}(q,a), & \text{change question answering}.
\end{cases}
\]

The adapter only restores predicate semantics already specified by the question. For example, an answer to “which land-cover type appeared?” is converted into an Add statement, whereas an answer that directly describes the dominant transition is parsed as a source-to-target statement. The adapter does not access the images, modify visual evidence, or change the scoring function. Captions and answers therefore share the same verifier.

The parser decomposes \(\tilde y\) into a set of atomic claims:

\[
\mathcal{C}(\tilde y)=\{c_i\}_{i=1}^{N}, \qquad
c_i=(e_i,d_i,\ell_i,r_i,\mathbf a_i),
\]

where \(e_i\) is a normalized entity, \(d_i\in\{\mathrm{Add},\mathrm{Remove},\mathrm{Modify},\mathrm{None},\mathrm{Unknown}\}\) denotes the change direction, \(\ell_i\) is an optional location, \(r_i\in\{\mathrm{Changed},\mathrm{Context},\mathrm{NoChange}\}\) specifies the claim role, and \(\mathbf a_i\) contains optional count and attribute constraints. Instead of treating a single scalar as the sole output, MGA reports

\[
\mathbf{s}(y)=
\bigl(S_{\mathrm{spa}},S_{\mathrm{temp}},S_{\mathrm{cov}},
S_{\mathrm{ctx}},U\bigr),
\]

corresponding to spatial support, temporal support, fact coverage, context support, and the unverifiable rate. A weighted Overall score is retained only as a supplementary summary.

## 3.2 Domain Claim Parsing and Semantic Normalization

Open-ended change language contains synonyms, number variations, passive constructions, and diverse change predicates. Directly sending raw mentions to a visual grounder makes queries such as `house`, `residential building`, and `structure` inconsistent, while keyword matching alone may confuse changed objects with contextual references. We therefore use an ontology-first parser with a lightweight model fallback.

Dataset labels, shared remote-sensing synonyms, and versioned surface-form dictionaries are merged into an entity ontology \(\Omega\). Each mention \(m\) is mapped to a canonical entity:

\[
e=\nu(m;\Omega).
\]

For example, `house/houses/residential area` is normalized to `building`, and `woodland/tree cover` is normalized to `tree`. The parser then binds entities and change predicates within local clauses. A phrase such as `converted from \(e_s\) to \(e_t\)` becomes \(\mathrm{Remove}(e_s)\) and \(\mathrm{Add}(e_t)\), whereas `road` in `near the road` is labeled as Context. A lightweight entity extractor is invoked only for ontology-missed spans, improving long-tail recall while limiting additional false positives.

Semantically enriched rewriting is not part of MGA inference. In the invariance experiment, a rewrite is accepted as claim preserving only if the canonical signatures before and after rewriting are identical:

\[
\operatorname{Sig}\!\left(\mathcal{C}(y)\right)
=
\operatorname{Sig}\!\left(\mathcal{C}(y')\right).
\]

Any change in entity, direction, location, count, or attribute is recorded as semantic drift rather than counted as evidence of linguistic invariance.

## 3.3 Three Evidence Modes and Entity-Wise Hybrid Routing

Let \(M^{t}_{e}\in\{0,1\}^{H\times W}\) denote the support mask of entity \(e\) at time \(t\). MGA uses two basic evidence sources. If bi-temporal semantic labels \(L^{t}\) contain category \(k(e)\), then

\[
M^{t,\mathrm{GT}}_{e}(p)
=\mathbb{1}\!\left[L^{t}(p)=k(e)\right].
\]

For an entity outside the annotation ontology, an open-vocabulary visual backend \(\mathcal{G}\) predicts

\[
M^{t,\mathrm{OV}}_{e}
=\mathcal{G}\!\left(I^{t},q(e)\right),
\]

where \(q(e)\) contains the normalized entity and, when calibrated, remote-sensing-specific query expansions.

We define three modes that share the same downstream verifier:

\[
M^{t,\mathrm{MGA\text{-}GT}}_{e}=M^{t,\mathrm{GT}}_{e},
\qquad
M^{t,\mathrm{MGA\text{-}OV}}_{e}=M^{t,\mathrm{OV}}_{e},
\]

\[
M^{t,\mathrm{MGA\text{-}Hybrid}}_{e}=
\begin{cases}
M^{t,\mathrm{GT}}_{e}, & e\in\Omega_{\mathrm{ann}},\\
M^{t,\mathrm{OV}}_{e}, & e\notin\Omega_{\mathrm{ann}}.
\end{cases}
\]

MGA-GT represents an ideal upper bound under complete semantic evidence. MGA-OV stress-tests the open-vocabulary visual backend. MGA-Hybrid is our primary configuration: it retains reliable spatial evidence for annotated categories while remaining able to verify entities outside the label space. Routing is performed per entity rather than per caption, so a building and an unannotated tree mentioned in the same sentence may use different evidence backends.

Our current controlled MGA-OV experiment still uses a semantic change ROI to isolate errors introduced by the entity grounder. It therefore evaluates fully open entity evidence, but should not be interpreted as a completely annotation-free deployment. Such a setting additionally requires an image-derived change ROI.

## 3.4 Bi-temporal Change Evidence

Entity presence in a single image does not establish a temporal direction. Given entity masks from both times, MGA constructs Add, Remove, and Modify evidence:

\[
A_e=M^{2}_{e}\cap\neg\mathcal{D}_{\rho}(M^{1}_{e}),
\]

\[
R_e=M^{1}_{e}\cap\neg\mathcal{D}_{\rho}(M^{2}_{e}),
\]

\[
X_e=M^{1}_{e}\oplus M^{2}_{e},
\]

where \(\mathcal{D}_{\rho}\) denotes morphological dilation with radius \(\rho\), which tolerates small registration and segmentation-boundary offsets. For a relation in which source entity \(e_s\) is replaced by target entity \(e_t\), we construct

\[
Q_{s\rightarrow t}
=
\mathcal{D}_{\delta}(R_{e_s})
\cap
\mathcal{D}_{\delta}(A_{e_t})
\cap
L_{\ell},
\]

where \(L_{\ell}\) is the spatial window specified by the claim. This intersection requires source removal and target addition to form a consistent relation in the same local change region, rather than merely finding the two entities somewhere in the image pair.

With binary or semantic change annotations, the observed change region is

\[
G=\mathbb{1}[L^{1}\neq L^{2}],
\]

or the dataset-provided binary change mask. For semantic transition experiments, the ideal source-to-target region is

\[
G_{s\rightarrow t}
=\mathbb{1}[L^{1}=k(e_s)]
\cap
\mathbb{1}[L^{2}=k(e_t)].
\]

## 3.5 Claim Verification and Component-Wise Scores

### Spatial support

Let \(E_i\) be the entity or relation evidence associated with claim \(c_i\). Spatial support is measured by evidence precision:

\[
S^{(i)}_{\mathrm{spa}}
=
\frac{|E_i\cap G_i|}
{|E_i|+\varepsilon}.
\]

It asks what fraction of the region used as textual evidence lies inside the observed change, thereby penalizing large irrelevant segmentations.

### Temporal support

For Add and Remove claims, temporal support measures novelty or disappearance within the change ROI:

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

Modify claims use the exclusive temporal difference:

\[
S^{(i)}_{\mathrm{temp,modify}}
=
\frac{|X_{e_i}\cap G_i|}
{|(M^{1}_{e_i}\cup M^{2}_{e_i})\cap G_i|+\varepsilon}.
\]

For source-to-target relations, we use

\[
S^{(i)}_{\mathrm{rel}}
=
\frac{|Q_{s\rightarrow t}\cap G|}
{|Q_{s\rightarrow t}|+\varepsilon}.
\]

### Coverage and verifiability

We decompose the ground-truth change mask into connected components
\(\{g_j\}_{j=1}^{K}\) that satisfy a minimum-area constraint. Let
\(E=\bigcup_i E_i\) be the union of claim evidence. Fact coverage is

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

When the visual backend cannot provide target evidence above the confidence threshold, MGA does not automatically interpret retrieval failure as a textual error. Instead, the claim is marked Unverifiable. The caption-level unverifiable rate is

\[
U=\frac{1}{N}\sum_{i=1}^{N}
\mathbb{1}[z_i=\mathrm{Unverifiable}].
\]

A claim is Contradicted if any available evidence axis is no higher than \(\tau_{\mathrm{con}}\), Supported if all available axes are at least \(\tau_{\mathrm{sup}}\), and Unverifiable otherwise. The current implementation uses \(\tau_{\mathrm{con}}=0.25\) and \(\tau_{\mathrm{sup}}=0.60\). Joint thresholding prevents a high spatial score from hiding a reversed Add/Remove direction.

For supplementary analysis, the available claim components can be summarized as

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

with \(w_s=0.65\) and \(w_t=0.35\) in the current implementation. Our primary experiments nevertheless report Spatial, Temporal, Coverage, and \(U\) separately instead of treating \(F_i\) or Overall as the sole quality measure.

## 3.6 Unified Inference and Task Adaptation

The complete procedure consists of six steps:

1. directly accept a caption or map a QA pair to declarative text with \(\mathcal A(q,a)\);
2. extract normalized atomic claims with the domain parser;
3. select bi-temporal entity evidence under MGA-GT, MGA-OV, or MGA-Hybrid;
4. construct Add, Remove, Modify, and source-to-target relation masks;
5. compute claim-level spatial and temporal support and assign Supported, Contradicted, or Unverifiable states;
6. aggregate Coverage, Context Support, and Unverifiable Rate into an output-level diagnostic.

Adapting from change captioning to open-ended change QA only adds the input adapter in Step 1; the evidence, equations, and thresholds in Steps 2–6 remain unchanged. The QA experiment therefore evaluates interface-level task transfer rather than introducing a separate metric tailored to question answering.
