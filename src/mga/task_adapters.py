"""Thin language-task adapters that preserve MGA's claim/evidence scorer."""

from __future__ import annotations

from collections.abc import Iterable

from mga.models import AtomicClaim
from mga.parsing.base import ClaimParser


def qa_answer_to_claims(
    *,
    question: str,
    answer: str,
    parser: ClaimParser,
    answer_type: str = "transition",
) -> tuple[AtomicClaim, ...]:
    """Convert a QA pair into the same declarative claims used for captions.

    The adapter supplies only the predicate implied by the question. Visual
    verification, evidence routing, thresholds, and aggregation remain
    unchanged.
    """

    clean_answer = " ".join(answer.strip().split())
    if not clean_answer:
        return ()
    if answer_type == "transition":
        declarative = clean_answer
    elif answer_type == "appeared_entity":
        declarative = f"{clean_answer} appeared after the change."
    elif answer_type == "removed_entity":
        declarative = f"{clean_answer} disappeared after the change."
    else:
        raise ValueError(f"Unsupported answer_type: {answer_type}")
    claims = tuple(parser.parse(declarative))
    return tuple(
        AtomicClaim(
            claim_id=claim.claim_id,
            text=f"Q: {question}\nA: {answer}",
            entity=claim.entity,
            role=claim.role,
            change_type=claim.change_type,
            location=claim.location,
            count=claim.count,
            attributes=claim.attributes,
            target_labels=claim.target_labels,
            metadata={**claim.metadata, "input_adapter": "qa_v1"},
        )
        for claim in claims
    )


def canonical_claim_signature(
    claims: Iterable[AtomicClaim | dict],
) -> tuple[tuple[object, ...], ...]:
    """Return the factual fields that must survive a style-only rewrite."""

    values = []
    for claim in claims:
        if isinstance(claim, AtomicClaim):
            values.append(
                (
                    claim.entity,
                    claim.role.value,
                    claim.change_type.value,
                    claim.location,
                    claim.count,
                    tuple(claim.attributes),
                    tuple(claim.target_labels),
                )
            )
        else:
            values.append(
                (
                    str(claim.get("entity", "")),
                    str(claim.get("role", "")),
                    str(claim.get("change_type", "")),
                    claim.get("location"),
                    claim.get("count"),
                    tuple(claim.get("attributes", ())),
                    tuple(int(item) for item in claim.get("target_labels", ())),
                )
            )
    return tuple(sorted(values, key=repr))


def is_claim_preserving_rewrite(
    *,
    original_claims: Iterable[AtomicClaim | dict],
    rewritten_text: str,
    parser: ClaimParser,
) -> tuple[bool, tuple[AtomicClaim, ...]]:
    """Accept a rewrite only when its canonical claim set is unchanged."""

    rewritten_claims = tuple(parser.parse(rewritten_text))
    return (
        canonical_claim_signature(original_claims)
        == canonical_claim_signature(rewritten_claims),
        rewritten_claims,
    )
