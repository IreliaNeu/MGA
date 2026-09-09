# 4 Experiments

> Consolidated working draft v2. Tables are rendered from archived local JSON. Independent human validity results are pending.

## 4.1 Research questions and setup

We evaluate how MGA-Hybrid translates bi-temporal evidence into factual diagnostics for change descriptions. The experiments examine entity-level routing under partial semantic annotation, sensitivity to controlled factual errors, and behavior on real system outputs under different perception conditions. Independent human evaluation will test whether these diagnostics correspond to human factual judgments.

The aligned LEVIR-MCI/LEVIR-CC evaluation contains 1,000 image pairs and 5,000 descriptions from Draft, Refined, Change-Agent, RSICCformer, and Chg2Cap, with five official references per scene. Draft and Refined represent processing stages rather than independent model families. SECOND-CC supplies 200 scenes and 600 base items for semantic evidence evaluation, plus a separate 1,600-item benchmark containing one factual description and seven perturbations per scene. Results from these populations remain separate. [Caption manifest](../../artifacts/baselines/p0-unified-2026-08-12/model_outputs_manifest.summary.json), [semantic benchmark](../../artifacts/semantic-change/second-cc-200-v1/evidence_summary.json), [error benchmark](../../artifacts/ablations/minimal-error-decomposition-secondcc-200-v1/summary.json).

MGA-Hybrid is the primary method; MGA-GT represents ideal semantic evidence, and MGA-OV tests open-vocabulary perception. GTClassLookup/MaskLabelOnly controls for direct class lookup. On LEVIR, `hybrid_mask_temporal` combines class-based spatial/coverage evidence with open temporal evidence. On SECOND, `known_gt_unknown_ov` routes pre/post masks by entity. These implementations share an evidence-availability principle but differ in annotation capabilities and scoring contracts. [LEVIR](../../artifacts/baselines/p0-unified-2026-08-12/segearth_unified_1000_summary.json), [SECOND](../../artifacts/semantic-change/second-cc-200-v1/evidence_summary.json).

We distinguish fact coverage from evaluation coverage. The former concerns known change facts covered by a description; the latter concerns items receiving numeric scores. SECOND's U denotes item-level abstention, whereas the real-caption table follows the archived aggregation of Claim states. Neutral AUC maps unavailable scores to 0.5 for statistical evaluation without changing the meaning of unverifiable. Unless specified otherwise, BAcc and FSR are conditional on numeric availability, and FSR uses scored negatives as its denominator. Oracle BAcc in the external-baseline table selects a threshold on that evaluation set and is descriptive, not a deployable calibrated result. [Availability protocol](../../artifacts/semantic-change/second-cc-200-v1/label-availability-curve-v2-verifiable/curve_summary.json), [baseline protocol](../../artifacts/baselines/p0-grounding-factual-2026-08-13/external-metric-comparison.json).

## 4.2 Evidence routing under partial annotation

We enumerate all 64 subsets of six semantic classes. Visible entities use semantic evidence; hidden entities use open masks. Table 1 averages over all subsets with the same cardinality. The source T1 and target T2 masks must exist and satisfy the archived confidence requirement for open evidence to be usable.

Table 1. Label availability; BAcc uses threshold 0.5.

| Visible classes | Subsets | Eval. coverage ↑ | Neutral AUC ↑ | BAcc ↑ | FSR ↓ | U ↓ |
| --- | --- | --- | --- | --- | --- | --- |
| 0/6 | 1 | 0.915 | 0.522 | 0.553 | 0.156 | 0.085 |
| 1/6 | 6 | 0.929 | 0.590 | 0.595 | 0.181 | 0.071 |
| 2/6 | 15 | 0.943 | 0.658 | 0.647 | 0.188 | 0.057 |
| 3/6 | 20 | 0.957 | 0.727 | 0.707 | 0.179 | 0.043 |
| 4/6 | 15 | 0.971 | 0.797 | 0.776 | 0.155 | 0.029 |
| 5/6 | 6 | 0.986 | 0.869 | 0.852 | 0.119 | 0.014 |
| 6/6 | 1 | 1.000 | 0.944 | 0.935 | 0.070 | 0.000 |

Source: [availability](../../artifacts/semantic-change/second-cc-200-v1/label-availability-curve-v2-verifiable/curve_summary.json)

Increasing reliable semantic evidence improves discrimination and numeric coverage. FSR is non-monotonic at low availability, so the benefit does not imply simultaneous improvement of every risk component.

Table 2 reports a separate, earlier four-route experiment without the explicit confidence-abstention gate used in Table 1. Its open-vocabulary route still uses a GT change ROI. The archived `oracle_all_class` provides the MGA-GT condition; implementation differences prevent interpreting every row as a strict monotonic bound under identical operators.

Table 2. Closed and hidden-class conditions; `open_set` hides tree, low vegetation, and water.

| Condition | Method | Eval. coverage ↑ | Neutral AUC ↑ | BAcc ↑ | FSR ↓ |
| --- | --- | --- | --- | --- | --- |
| closed_set | GTClassLookup | 1.000 | 0.875 | 0.875 | 0.250 |
| closed_set | MGA-OV + GT-ROI | 1.000 | 0.580 | 0.560 | 0.130 |
| closed_set | MGA-Hybrid | 1.000 | 0.944 | 0.935 | 0.070 |
| closed_set | MGA-GT (oracle) | 1.000 | 0.958 | 0.958 | 0.075 |
| hidden_class | GTClassLookup | 0.195 | 0.636 | 0.886 | 0.229 |
| hidden_class | MGA-OV + GT-ROI | 1.000 | 0.580 | 0.560 | 0.130 |
| hidden_class | MGA-Hybrid | 1.000 | 0.711 | 0.702 | 0.180 |
| hidden_class | MGA-GT (oracle) | 1.000 | 0.958 | 0.958 | 0.075 |

Source: [evidence](../../artifacts/semantic-change/second-cc-200-v1/evidence_summary.json)

Direct lookup loses coverage when classes are hidden. Hybrid retains open evidence and verifies the local source-to-target relation, separating evidence availability from factual discrimination.

## 4.3 Controlled errors and factual baselines

Each perturbation targets one specified factual factor: direction, entity, added hallucination, location, no-change, omission, or relation. Table 3 uses `diagnostic_score = evidence_score × atomic_fact_coverage`; the coverage term relies on the controlled fact graph. Strict pair accuracy requires the factual description to score higher, assigning no success to ties. Independent human validation of perturbation validity is pending.

Table 3. MGA-Hybrid on 200 pairs per error type; BAcc/FSR threshold 0.5.

| Error | Strict pair acc. ↑ | Neutral AUC ↑ | BAcc ↑ | FSR ↓ | U ↓ |
| --- | --- | --- | --- | --- | --- |
| direction | 0.735 | 0.868 | 0.860 | 0.000 | 0.000 |
| entity | 0.735 | 0.823 | 0.860 | 0.000 | 0.000 |
| hallucination | 0.385 | 0.688 | 0.682 | 0.355 | 0.000 |
| location | 0.410 | 0.673 | 0.670 | 0.380 | 0.000 |
| no-change | 0.742 | 0.866 | 0.860 | 0.000 | 0.010 |
| omission | 0.730 | 0.742 | 0.860 | 0.000 | 0.000 |
| relation | 0.735 | 0.868 | 0.860 | 0.000 | 0.000 |

Source: [errors](../../artifacts/ablations/minimal-error-decomposition-secondcc-200-v1/summary.json)

The diagnostic pattern distinguishes the targeted error types. Location and added hallucination exhibit higher false support rates, motivating local-evidence analysis. Omission performance depends on fact-graph coverage and does not establish detection of unexpressed facts from reference-free evidence scores.

On the same 1,600 items, ALOHa-local uses the official local object-matching variant with SpaCy-small and MPNet. FMScore-Qwen retains the factual yes/no protocol while substituting Qwen3-VL-2B for the original backend.

Table 4. Factual discrimination with 2,000 scene bootstrap replicates, seed 20260813.

| Method | ROC-AUC ↑ | Scene bootstrap 95% CI | Oracle BAcc ↑ |
| --- | --- | --- | --- |
| ALOHa-local | 0.578 | [0.566, 0.590] | 0.660 |
| FMScore-Qwen | 0.823 | [0.812, 0.833] | 0.823 |
| MGA-Hybrid | 0.790 | [0.756, 0.821] | 0.809 |

Source: [external](../../artifacts/baselines/p0-grounding-factual-2026-08-13/external-metric-comparison.json)

| Paired contrast | AUC difference | Scene bootstrap 95% CI |
| --- | --- | --- |
| MGA-Hybrid_minus_ALOHa | 0.211 | [0.174, 0.248] |
| MGA-Hybrid_minus_FMScore-Qwen | -0.033 | [-0.070, 0.002] |

Source: [external](../../artifacts/baselines/p0-grounding-factual-2026-08-13/external-metric-comparison.json)

The paired AUC interval favors MGA-Hybrid over ALOHa-local. The comparison with FMScore-Qwen spans zero and does not establish an overall AUC advantage. The intended contribution is bi-temporal verification of candidate Claims and interpretable diagnostics; incremental validity on real descriptions requires independent human evidence.

## 4.4 Real system outputs and reference metrics

All five candidate sources use the same evaluation pipeline. Table 5 describes evidence-support distributions rather than caption-generator accuracy rankings. Overall is retained as an auxiliary historical aggregation; interpretation emphasizes components and Parser coverage.

Table 5. MGA-Hybrid on 1,000 aligned image pairs.

| System | Captions | Faithfulness | Fact coverage | Temporal | Overall | U | Parser no-claim rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Change-Agent | 1000 | 0.914 | 0.893 | 0.887 | 0.896 | 0.025 | 0.011 |
| Chg2Cap | 1000 | 0.906 | 0.876 | 0.882 | 0.892 | 0.016 | 0.003 |
| Draft | 1000 | 0.884 | 0.867 | 0.803 | 0.861 | 0.037 | 0.019 |
| RSICCformer | 1000 | 0.885 | 0.872 | 0.823 | 0.874 | 0.015 | 0.003 |
| Refined | 1000 | 0.798 | 0.744 | 0.696 | 0.736 | 0.083 | 0.065 |

Source: [unified](../../artifacts/baselines/p0-unified-2026-08-12/segearth_unified_1000_summary.json); [manifest](../../artifacts/baselines/p0-unified-2026-08-12/model_outputs_manifest.summary.json)

Refined has a higher no-Claim rate, so its support distribution must be interpreted jointly with parsing availability. An Oracle Claim ablation will hold visual evidence fixed to separate parsing from verification errors.

Reference metrics are recomputed for Draft/Refined on the aligned scenes. Scores from other systems' publications are not mixed into this same-scene comparison.

Table 6. Reference metrics under matched scenes and references.

| System | BLEU-4 | METEOR | ROUGE-L | CIDEr |
| --- | --- | --- | --- | --- |
| Draft | 0.538 | 0.374 | 0.725 | 1.216 |
| Refined | 0.427 | 0.326 | 0.638 | 0.962 |

Source: [text](../../artifacts/baselines/p0-unified-2026-08-12/text_metric_summary.json)

| System | SPICE | BERTScore-F1 | BiTemporal CLIP mean | S*m | SPIDEr |
| --- | --- | --- | --- | --- | --- |
| Draft | 0.309 | 0.961 | 0.239 | 0.713 | 0.762 |
| Refined | 0.257 | 0.948 | 0.242 | 0.588 | 0.609 |

Source: [spice](../../artifacts/baselines/p0-unified-2026-08-12/spice_summary.json); [bert](../../artifacts/baselines/p0-unified-2026-08-12/bertscore_summary.json); [clip](../../artifacts/baselines/p0-unified-2026-08-12/clipscore_summary.json); [composites](../../artifacts/baselines/p0-grounding-factual-2026-08-13/rscc-composite-metrics.json)

The CLIP baseline averages independent T1/T2 image-text cosine similarities and does not explicitly encode change direction. Reference composites do not add bi-temporal evidence.

Table 7. Inter-metric correlations and effective sample sizes.

| Metric | MGA component | n | Spearman ρ | Kendall τ |
| --- | --- | --- | --- | --- |
| BLEU-4 | MGA-Overall | 2000 | 0.717 | 0.578 |
| BLEU-4 | MGA-Temporal | 1136 | 0.435 | 0.323 |
| CIDEr | MGA-Overall | 2000 | 0.714 | 0.581 |
| CIDEr | MGA-Temporal | 1136 | 0.457 | 0.341 |
| BERTScore-F1 | MGA-Overall | 2000 | 0.732 | 0.597 |
| BERTScore-F1 | MGA-Temporal | 1136 | 0.419 | 0.309 |
| BiTemporal-CLIP-mean | MGA-Overall | 2000 | -0.400 | -0.292 |
| BiTemporal-CLIP-mean | MGA-Temporal | 1136 | -0.095 | -0.070 |

Source: [alignment](../../artifacts/baselines/p0-unified-2026-08-12/unified_metric_alignment.json)

Temporal exhibits a different association structure from Overall, but their effective populations also differ. This motivates a complementarity hypothesis; lower correlation alone does not demonstrate useful additional information or human validity.

## 4.5 Perception conditions, Parser, and selective evaluation

ROI thresholds are selected on 97 development scenes and evaluated on 103 disjoint test scenes. Table 8 reports the Hybrid route. Predicted-CD uses cross-domain ChangeFormer evidence; No-ROI and GT-ROI provide gating controls.

Table 8. Hybrid ROI comparison using development-selected thresholds.

| ROI | Eval. coverage ↑ | Neutral AUC ↑ | BAcc ↑ | FSR ↓ |
| --- | --- | --- | --- | --- |
| feature_difference_roi | 0.968 | 0.720 | 0.737 | 0.289 |
| no_roi | 0.968 | 0.748 | 0.746 | 0.309 |
| oracle_gt_roi | 0.968 | 0.739 | 0.729 | 0.175 |
| predicted_cd_roi | 0.968 | 0.693 | 0.713 | 0.258 |

Source: [roi](../../artifacts/ablations/predicted-roi-calibration-secondcc-200-v1/hybrid_calibration_summary.json)

Predicted ROI reduces false support in this setting without improving overall Neutral AUC. Hybrid still uses available semantic classes, so these numbers do not represent a fully annotation-free system.

Table 9 compares Grounding DINO Tiny and Base on 500 scenes and 2,500 descriptions with identical Claims, queries, box threshold 0.30, and text threshold 0.25. The component changes characterize perception conservatism and verifiability; the primary archived experiments retain their SegEarth backend.

| Component | Base minus Tiny (five-system macro mean) |
| --- | --- |
| coverage | -0.158 |
| faithfulness | 0.179 |
| overall | 0.081 |
| temporal | 0.578 |
| unverifiable_rate | 0.213 |

Source: [dino](../../artifacts/baselines/p0-grounding-factual-2026-08-13/grounding-dino-size-ablation.json)

Table 10 separates base ontology parsing from parsing with configured surface forms on 1,200 controlled items. High configured-ontology coverage describes the specified expression inventory, not independently measured open-language generalization.

| Parser setting | Exact match ↑ | Precision ↑ | Recall ↑ | F1 ↑ |
| --- | --- | --- | --- | --- |
| ontology_only | 0.500 | 1.000 | 0.500 | 0.667 |
| ontology_gliner | 0.518 | 0.947 | 0.650 | 0.770 |
| configured_ontology | 1.000 | 1.000 | 1.000 | 1.000 |
| configured_ontology_gliner | 0.927 | 0.965 | 1.000 | 0.982 |

Source: [parser](../../artifacts/semantic-change/second-cc-200-v1/parser_report_compact.json); [parser_configured](../../artifacts/semantic-change/second-cc-200-v1/parser_report_v3.json)

Selective evaluation retains items by visual confidence and includes all confidence ties at the boundary. Table 11 reports actual rather than requested coverage, together with supported precision. These are descriptive operating points; deployment thresholds require independent selection.

| Selection | Coverage | Accuracy ↑ | FSR ↓ | Supported precision ↑ |
| --- | --- | --- | --- | --- |
| All scored | 0.999 | 0.873 | 0.105 | 0.495 |
| Requested 0.10 | 0.193 | 0.961 | 0.041 | 0.784 |
| Requested 0.25 | 0.251 | 0.945 | 0.058 | 0.726 |
| Requested 0.50 | 0.504 | 0.872 | 0.123 | 0.533 |
| Requested 0.75 | 0.753 | 0.883 | 0.106 | 0.513 |

Source: [selective](../../artifacts/ablations/selective-prediction-minimal-errors-200-v1/visual_confidence_summary.json)

As supplementary mechanism evidence, 72% of 50 rewrites pass canonical Claim equivalence gating; accepted rewrites have state agreement 1 and mean score difference 0. This result is conditional on verified Claim equivalence. The 40 free-form QA outputs have zero Parser success, exact transition accuracy, and Hybrid score coverage; QA therefore remains an interface experiment rather than evidence of successful task generalization. [Rewrite and QA summary](../../artifacts/qwen3-vl-supplement-v1/summary.json).

## 4.6 Human validity: pilot and held-out evaluation

The historical pilot contains 50 scenes and three raters. Caption alignment matches 149 of 150 descriptions, leaving 49 complete scenes; one Refined caption differs from the score manifest. Table 12 retains effective sample sizes to avoid interpreting different-support AUCs as paired advantages. [Alignment audit](../../artifacts/ablations/hybrid-human-50x3-3raters-v1/human_alignment_summary.json).

| Mode | Component | n | ROC-AUC ↑ | BAcc @ 0.60 ↑ |
| --- | --- | --- | --- | --- |
| full_target | overall | 149 | 0.466 | 0.584 |
| full_target | temporal | 93 | 0.782 | 0.739 |
| hybrid_mask_temporal | overall | 149 | 0.512 | 0.639 |
| hybrid_mask_temporal | temporal | 93 | 0.782 | 0.739 |
| mask_label_only | overall | 149 | 0.593 | 0.644 |
| mask_label_only | temporal | 0 | — | — |

Source: [human](../../artifacts/ablations/hybrid-human-50x3-3raters-v1/human_alignment_summary.json)

Preference agreement has Fleiss κ=0.315, and the GT-omission question has negative agreement. The planned protocol separates factual correctness, insufficient evidence, inapplicability, and GT-coverage auditing, preserving pre-adjudication disagreement. [Rater summary](../../artifacts/human-eval/three-rater-v1/summary.json).

**Independent human validity is pending.** Approximately five raters and 200 samples are planned; the image-pair unit and candidate allocation are not yet finalized. No simulated human outcomes are reported. Once annotations are available, comparisons will use matched scenes, candidates, and human dimensions, reporting AUC, fixed-threshold BAcc, Spearman/Kendall, within-scene pairwise accuracy, inter-rater agreement, and scene bootstrap intervals. Any threshold selection or metric combination will use development data only.

## 4.7 Findings

The current experiments support entity-level routing of partial semantic annotation and open perception for bi-temporal Claim diagnostics. Real outputs and perception controls show why evidence provenance, Parser coverage, and unverifiable states belong in the evaluation report. Independent human evaluation will determine the strength of alignment with human factual judgments and incremental value over reference and factual baselines.
