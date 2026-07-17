from __future__ import annotations

import numpy as np

from mga.models import (
    AtomicClaim,
    ChangeType,
    ClaimRole,
    ClaimStatus,
    GroundingEvidence,
    SampleRecord,
)
from mga.scoring import LegacyMGAScorer, MGAV2Scorer


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
