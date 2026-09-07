# 4 Experiments

> Consolidated working draft v2. Tables are rendered from archived local JSON. Independent human validity results are pending.

## 4.1 Research questions and setup

We evaluate how MGA-Hybrid translates bi-temporal evidence into factual diagnostics for change descriptions. The experiments examine entity-level routing under partial semantic annotation, sensitivity to controlled factual errors, and behavior on real system outputs under different perception conditions. Independent human evaluation will test whether these diagnostics correspond to human factual judgments.

The aligned LEVIR-MCI/LEVIR-CC evaluation contains 1,000 image pairs and 5,000 descriptions from Draft, Refined, Change-Agent, RSICCformer, and Chg2Cap, with five official references per scene. Draft and Refined represent processing stages rather than independent model families. SECOND-CC supplies 200 scenes and 600 base items for semantic evidence evaluation, plus a separate 1,600-item benchmark containing one factual description and seven perturbations per scene. Results from these populations remain separate. [Caption manifest]({{source:manifest}}), [semantic benchmark]({{source:evidence}}), [error benchmark]({{source:errors}}).

MGA-Hybrid is the primary method; MGA-GT represents ideal semantic evidence, and MGA-OV tests open-vocabulary perception. GTClassLookup/MaskLabelOnly controls for direct class lookup. On LEVIR, `hybrid_mask_temporal` combines class-based spatial/coverage evidence with open temporal evidence. On SECOND, `known_gt_unknown_ov` routes pre/post masks by entity. These implementations share an evidence-availability principle but differ in annotation capabilities and scoring contracts. [LEVIR]({{source:unified}}), [SECOND]({{source:evidence}}).

We distinguish fact coverage from evaluation coverage. The former concerns known change facts covered by a description; the latter concerns items receiving numeric scores. SECOND's U denotes item-level abstention, whereas the real-caption table follows the archived aggregation of Claim states. Neutral AUC maps unavailable scores to 0.5 for statistical evaluation without changing the meaning of unverifiable. Unless specified otherwise, BAcc and FSR are conditional on numeric availability, and FSR uses scored negatives as its denominator. Oracle BAcc in the external-baseline table selects a threshold on that evaluation set and is descriptive, not a deployable calibrated result. [Availability protocol]({{source:availability}}), [baseline protocol]({{source:external}}).

## 4.2 Evidence routing under partial annotation

We enumerate all 64 subsets of six semantic classes. Visible entities use semantic evidence; hidden entities use open masks. Table 1 averages over all subsets with the same cardinality. The source T1 and target T2 masks must exist and satisfy the archived confidence requirement for open evidence to be usable.

Table 1. Label availability; BAcc uses threshold 0.5.

{{table:availability}}

Increasing reliable semantic evidence improves discrimination and numeric coverage. FSR is non-monotonic at low availability, so the benefit does not imply simultaneous improvement of every risk component.

Table 2 reports a separate, earlier four-route experiment without the explicit confidence-abstention gate used in Table 1. Its open-vocabulary route still uses a GT change ROI. The archived `oracle_all_class` provides the MGA-GT condition; implementation differences prevent interpreting every row as a strict monotonic bound under identical operators.

Table 2. Closed and hidden-class conditions; `open_set` hides tree, low vegetation, and water.

{{table:routes}}

Direct lookup loses coverage when classes are hidden. Hybrid retains open evidence and verifies the local source-to-target relation, separating evidence availability from factual discrimination.

## 4.3 Controlled errors and factual baselines

Each perturbation targets one specified factual factor: direction, entity, added hallucination, location, no-change, omission, or relation. Table 3 uses `diagnostic_score = evidence_score × atomic_fact_coverage`; the coverage term relies on the controlled fact graph. Strict pair accuracy requires the factual description to score higher, assigning no success to ties. Independent human validation of perturbation validity is pending.

Table 3. MGA-Hybrid on 200 pairs per error type; BAcc/FSR threshold 0.5.

{{table:errors}}

The diagnostic pattern distinguishes the targeted error types. Location and added hallucination exhibit higher false support rates, motivating local-evidence analysis. Omission performance depends on fact-graph coverage and does not establish detection of unexpressed facts from reference-free evidence scores.

On the same 1,600 items, ALOHa-local uses the official local object-matching variant with SpaCy-small and MPNet. FMScore-Qwen retains the factual yes/no protocol while substituting Qwen3-VL-2B for the original backend.

Table 4. Factual discrimination with 2,000 scene bootstrap replicates, seed 20260813.

{{table:external}}

{{table:deltas}}

The paired AUC interval favors MGA-Hybrid over ALOHa-local. The comparison with FMScore-Qwen spans zero and does not establish an overall AUC advantage. The intended contribution is bi-temporal verification of candidate Claims and interpretable diagnostics; incremental validity on real descriptions requires independent human evidence.

## 4.4 Real system outputs and reference metrics

All five candidate sources use the same evaluation pipeline. Table 5 describes evidence-support distributions rather than caption-generator accuracy rankings. Overall is retained as an auxiliary historical aggregation; interpretation emphasizes components and Parser coverage.

Table 5. MGA-Hybrid on 1,000 aligned image pairs.

{{table:unified}}

Refined has a higher no-Claim rate, so its support distribution must be interpreted jointly with parsing availability. An Oracle Claim ablation will hold visual evidence fixed to separate parsing from verification errors.

Reference metrics are recomputed for Draft/Refined on the aligned scenes. Scores from other systems' publications are not mixed into this same-scene comparison.

Table 6. Reference metrics under matched scenes and references.

{{table:text}}

{{table:semantic_text}}

The CLIP baseline averages independent T1/T2 image-text cosine similarities and does not explicitly encode change direction. Reference composites do not add bi-temporal evidence.

Table 7. Inter-metric correlations and effective sample sizes.

{{table:correlations}}

Temporal exhibits a different association structure from Overall, but their effective populations also differ. This motivates a complementarity hypothesis; lower correlation alone does not demonstrate useful additional information or human validity.

## 4.5 Perception conditions, Parser, and selective evaluation

ROI thresholds are selected on 97 development scenes and evaluated on 103 disjoint test scenes. Table 8 reports the Hybrid route. Predicted-CD uses cross-domain ChangeFormer evidence; No-ROI and GT-ROI provide gating controls.

Table 8. Hybrid ROI comparison using development-selected thresholds.

{{table:roi}}

Predicted ROI reduces false support in this setting without improving overall Neutral AUC. Hybrid still uses available semantic classes, so these numbers do not represent a fully annotation-free system.

Table 9 compares Grounding DINO Tiny and Base on 500 scenes and 2,500 descriptions with identical Claims, queries, box threshold 0.30, and text threshold 0.25. The component changes characterize perception conservatism and verifiability; the primary archived experiments retain their SegEarth backend.

{{table:dino}}

Table 10 separates base ontology parsing from parsing with configured surface forms on 1,200 controlled items. High configured-ontology coverage describes the specified expression inventory, not independently measured open-language generalization.

{{table:parser}}

Selective evaluation retains items by visual confidence and includes all confidence ties at the boundary. Table 11 reports actual rather than requested coverage, together with supported precision. These are descriptive operating points; deployment thresholds require independent selection.

{{table:selective}}

As supplementary mechanism evidence, 72% of 50 rewrites pass canonical Claim equivalence gating; accepted rewrites have state agreement 1 and mean score difference 0. This result is conditional on verified Claim equivalence. The 40 free-form QA outputs have zero Parser success, exact transition accuracy, and Hybrid score coverage; QA therefore remains an interface experiment rather than evidence of successful task generalization. [Rewrite and QA summary]({{source:qwen}}).

## 4.6 Human validity: pilot and held-out evaluation

The historical pilot contains 50 scenes and three raters. Caption alignment matches 149 of 150 descriptions, leaving 49 complete scenes; one Refined caption differs from the score manifest. Table 12 retains effective sample sizes to avoid interpreting different-support AUCs as paired advantages. [Alignment audit]({{source:human}}).

{{table:pilot}}

Preference agreement has Fleiss κ=0.315, and the GT-omission question has negative agreement. The planned protocol separates factual correctness, insufficient evidence, inapplicability, and GT-coverage auditing, preserving pre-adjudication disagreement. [Rater summary]({{source:raters}}).

**Independent human validity is pending.** Approximately five raters and 200 samples are planned; the image-pair unit and candidate allocation are not yet finalized. No simulated human outcomes are reported. Once annotations are available, comparisons will use matched scenes, candidates, and human dimensions, reporting AUC, fixed-threshold BAcc, Spearman/Kendall, within-scene pairwise accuracy, inter-rater agreement, and scene bootstrap intervals. Any threshold selection or metric combination will use development data only.

## 4.7 Findings

The current experiments support entity-level routing of partial semantic annotation and open perception for bi-temporal Claim diagnostics. Real outputs and perception controls show why evidence provenance, Parser coverage, and unverifiable states belong in the evaluation report. Independent human evaluation will determine the strength of alignment with human factual judgments and incremental value over reference and factual baselines.
