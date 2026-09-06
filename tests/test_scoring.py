from __future__ import annotations

import numpy as np

from mga.models import (
    AtomicClaim,
    ChangeType,
    ClaimRole,
    ClaimStatus,
    EvidenceMode,
    GroundingEvidence,
    SampleRecord,
)
from mga.scoring import LegacyMGAScorer, MGAV2Config, MGAV2Scorer


def record(*claims: AtomicClaim, model: str = "test") -> SampleRecord:
    return SampleRecord(
        sample_id="test_000001",
        model=model,
        caption="caption",
        pre_image="pre.png",
        post_image="post.png",
        change_mask="change.png",
        claims=claims,
    )


def changed_claim(change_type: ChangeType = ChangeType.ADD) -> AtomicClaim:
    return AtomicClaim(
        claim_id="c001",
        text="a house appears",
        entity="house",
        role=ClaimRole.CHANGED,
        change_type=change_type,
    )


def test_supported_addition_scores_all_axes() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[2:5, 2:5] = True
    evidence = GroundingEvidence(
        pre_mask=np.zeros_like(change),
        post_mask=change.copy(),
        pre_confidence=0.0,
        post_confidence=0.95,
    )

    result = MGAV2Scorer().score(record(changed_claim()), change, {"c001": evidence})

    assert result.faithfulness == 1.0
    assert result.coverage == 1.0
    assert result.temporal == 1.0
    assert result.claim_scores[0].status == ClaimStatus.SUPPORTED


def test_feedback_hallucination_in_no_change_scene_is_contradicted() -> None:
    change = np.zeros((8, 8), dtype=bool)
    no_change = AtomicClaim(
        claim_id="c001",
        text="the two scenes seem identical",
        entity="scene",
        role=ClaimRole.NO_CHANGE,
        change_type=ChangeType.NONE,
    )
    draft = MGAV2Scorer().score(record(no_change, model="Draft"), change, {})
    guided = MGAV2Scorer().score(
        record(changed_claim(), model="Guided"),
        change,
        {"c001": GroundingEvidence()},
    )

    assert draft.faithfulness == 1.0
    assert draft.coverage == 1.0
    assert draft.claim_scores[0].status == ClaimStatus.SUPPORTED
    assert guided.faithfulness == 0.0
    assert guided.coverage == 0.0
    assert guided.claim_scores[0].status == ClaimStatus.CONTRADICTED


def test_v2_does_not_remove_false_positive_components_before_scoring() -> None:
    change = np.zeros((10, 10), dtype=bool)
    change[1:3, 1:3] = True
    support = change.copy()
    support[6:9, 6:9] = True
    evidence = GroundingEvidence(
        pre_mask=np.zeros_like(change),
        post_mask=support,
        post_confidence=0.9,
    )
    sample = record(changed_claim())

    legacy = LegacyMGAScorer().score(sample, change, {"c001": evidence})
    v2 = MGAV2Scorer().score(sample, change, {"c001": evidence})

    assert legacy.changed_score == 1.0
    assert v2.claim_scores[0].spatial_support == 4 / 13
    assert v2.faithfulness is not None and v2.faithfulness < legacy.changed_score


def test_context_overlap_is_not_automatically_penalized_in_v2() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[2:5, 2:5] = True
    context = AtomicClaim(
        claim_id="c001",
        text="a house near the road",
        entity="road",
        role=ClaimRole.CONTEXT,
        change_type=ChangeType.NONE,
    )
    evidence = GroundingEvidence(post_mask=change.copy(), post_confidence=0.9)

    result = MGAV2Scorer().score(record(context), change, {"c001": evidence})

    assert result.context_support == 0.9
    assert result.claim_scores[0].status == ClaimStatus.SUPPORTED


def test_low_confidence_grounding_is_unverifiable() -> None:
    change = np.ones((4, 4), dtype=bool)
    evidence = GroundingEvidence(post_mask=change, post_confidence=0.1)
    result = MGAV2Scorer().score(record(changed_claim()), change, {"c001": evidence})

    assert result.faithfulness is None
    assert result.unverifiable_rate == 1.0
    assert result.claim_scores[0].status == ClaimStatus.UNVERIFIABLE


def test_claim_target_labels_select_the_matching_reference_class() -> None:
    labels = np.zeros((8, 8), dtype=np.uint8)
    labels[1:3, 1:3] = 1
    labels[4:7, 4:7] = 2
    building = AtomicClaim(
        claim_id="c001",
        text="a house appears",
        entity="building",
        role=ClaimRole.CHANGED,
        change_type=ChangeType.ADD,
        target_labels=(2,),
    )
    evidence = GroundingEvidence(
        pre_mask=np.zeros_like(labels, dtype=bool),
        post_mask=labels == 2,
        post_confidence=0.95,
    )
    sample = SampleRecord(
        sample_id="test_000001",
        model="test",
        caption="a house appears",
        pre_image="pre.png",
        post_image="post.png",
        change_mask="change.png",
        claims=(building,),
        metadata={"mask_labels": [1, 2]},
    )

    result = MGAV2Scorer().score(sample, labels, {"c001": evidence})

    assert result.claim_scores[0].spatial_support == 1.0
    assert result.claim_scores[0].status == ClaimStatus.SUPPORTED


def test_temporal_delta_uses_post_minus_pre_for_additions() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[2:6, 2:6] = True
    pre = np.zeros_like(change)
    pre[2:4, 2:6] = True
    post = change.copy()
    evidence = GroundingEvidence(
        pre_mask=pre,
        post_mask=post,
        pre_confidence=0.9,
        post_confidence=0.9,
    )
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode=EvidenceMode.TEMPORAL_DELTA))

    result = scorer.score(record(changed_claim()), change, {"c001": evidence})

    claim_score = result.claim_scores[0]
    assert claim_score.spatial_support == 1.0
    assert claim_score.temporal_support == 0.5
    assert result.coverage == 1.0
    assert result.metadata["evidence_mode"] == "temporal_delta"


def test_temporal_delta_uses_pre_minus_post_for_removals() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[2:6, 2:6] = True
    post = np.zeros_like(change)
    post[2:4, 2:6] = True
    pre = change.copy()
    evidence = GroundingEvidence(
        pre_mask=pre,
        post_mask=post,
        pre_confidence=0.9,
        post_confidence=0.9,
    )
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="temporal_delta"))

    result = scorer.score(
        record(changed_claim(ChangeType.REMOVE)), change, {"c001": evidence}
    )

    assert result.claim_scores[0].spatial_support == 1.0
    assert result.claim_scores[0].temporal_support == 0.5


def test_temporal_delta_uses_xor_for_modifications() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[2:6, 2:6] = True
    pre = np.zeros_like(change)
    post = np.zeros_like(change)
    pre[2:4, 2:6] = True
    post[4:6, 2:6] = True
    evidence = GroundingEvidence(
        pre_mask=pre,
        post_mask=post,
        pre_confidence=0.9,
        post_confidence=0.9,
    )
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="temporal_delta"))

    result = scorer.score(
        record(changed_claim(ChangeType.MODIFY)), change, {"c001": evidence}
    )

    assert result.claim_scores[0].spatial_support == 1.0
    assert result.claim_scores[0].temporal_support == 1.0


def test_gt_roi_gated_discards_support_outside_reference_change() -> None:
    change = np.zeros((8, 8), dtype=bool)
    change[1:3, 1:3] = True
    post = np.zeros_like(change)
    post[5:7, 5:7] = True
    evidence = GroundingEvidence(post_mask=post, post_confidence=0.9)
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="gt_roi_gated"))

    result = scorer.score(record(changed_claim()), change, {"c001": evidence})

    assert result.faithfulness is None
    assert result.claim_scores[0].status == ClaimStatus.UNVERIFIABLE


def test_mask_label_only_scores_parser_class_without_grounder() -> None:
    labels = np.zeros((8, 8), dtype=np.uint8)
    labels[1:3, 1:3] = 1
    labels[4:7, 4:7] = 2
    building = AtomicClaim(
        claim_id="c001",
        text="a building appears",
        entity="building",
        role=ClaimRole.CHANGED,
        change_type=ChangeType.ADD,
        target_labels=(2,),
    )
    sample = SampleRecord(
        sample_id="test_000001",
        model="test",
        caption="a building appears",
        pre_image="pre.png",
        post_image="post.png",
        change_mask="change.png",
        claims=(building,),
        metadata={"mask_labels": [1, 2]},
    )
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="mask_label_only"))

    result = scorer.score(sample, labels, {})

    assert result.faithfulness == 1.0
    assert result.coverage == 0.5
    assert result.temporal is None
    assert result.claim_scores[0].status == ClaimStatus.SUPPORTED
    assert result.metadata["evidence_mode"] == "mask_label_only"


def test_mask_label_only_requires_parser_target_labels() -> None:
    change = np.ones((4, 4), dtype=bool)
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="mask_label_only"))

    result = scorer.score(record(changed_claim()), change, {})

    assert result.faithfulness is None
    assert result.claim_scores[0].status == ClaimStatus.UNVERIFIABLE


def test_hybrid_uses_gt_class_for_spatial_and_segearth_for_temporal() -> None:
    labels = np.zeros((8, 8), dtype=np.uint8)
    labels[1:3, 1:3] = 1
    labels[4:7, 4:7] = 2
    building = AtomicClaim(
        claim_id="c001",
        text="a building appears",
        entity="building",
        role=ClaimRole.CHANGED,
        change_type=ChangeType.ADD,
        target_labels=(2,),
    )
    post = labels == 2
    post[0:2, 6:8] = True
    evidence = GroundingEvidence(
        pre_mask=np.zeros_like(labels, dtype=bool),
        post_mask=post,
        post_confidence=0.95,
    )
    sample = SampleRecord(
        sample_id="test_000001",
        model="test",
        caption="a building appears",
        pre_image="pre.png",
        post_image="post.png",
        change_mask="change.png",
        claims=(building,),
        metadata={"mask_labels": [1, 2]},
    )
    scorer = MGAV2Scorer(
        MGAV2Config(evidence_mode=EvidenceMode.HYBRID_MASK_TEMPORAL)
    )

    result = scorer.score(sample, labels, {"c001": evidence})

    assert result.claim_scores[0].spatial_support == 1.0
    assert result.claim_scores[0].temporal_support == 1.0
    assert result.claim_scores[0].status == ClaimStatus.SUPPORTED
    assert result.coverage == 0.5


def test_hybrid_preserves_spatial_but_marks_missing_temporal_unverifiable() -> None:
    labels = np.zeros((8, 8), dtype=np.uint8)
    labels[4:7, 4:7] = 2
    building = AtomicClaim(
        claim_id="c001",
        text="a building appears",
        entity="building",
        role=ClaimRole.CHANGED,
        change_type=ChangeType.ADD,
        target_labels=(2,),
    )
    sample = SampleRecord(
        sample_id="test_000001",
        model="test",
        caption="a building appears",
        pre_image="pre.png",
        post_image="post.png",
        change_mask="change.png",
        claims=(building,),
        metadata={"mask_labels": [1, 2]},
    )
    scorer = MGAV2Scorer(MGAV2Config(evidence_mode="hybrid_mask_temporal"))

    result = scorer.score(sample, labels, {})

    claim_score = result.claim_scores[0]
    assert claim_score.spatial_support == 1.0
    assert claim_score.temporal_support is None
    assert claim_score.faithfulness is None
    assert claim_score.status == ClaimStatus.UNVERIFIABLE
    assert result.coverage == 1.0
