"""Corrected four-route evidence scoring for semantic-change experiments."""

from __future__ import annotations

from typing import Any

import numpy as np

from mga import evidence_routing as base

EVIDENCE_MODES = base.EVIDENCE_MODES
grounder_diagnostics = base.grounder_diagnostics
summarize_scores = base.summarize_scores


def score_evidence_modes(
    *,
    claims: list[dict[str, Any]],
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    visible_entities: set[str],
    open_vocab: dict[str, dict[str, Any]],
) -> dict[str, float | None]:
    """Score lookup, open-vocabulary, routed hybrid, and full-GT oracle.

    Unlike the initial pilot implementation, a valid query with no supported
    relation receives 0 rather than abstaining. The hybrid also routes each
    entity independently: a visible class uses its semantic GT mask, whereas
    a hidden class uses the open-vocabulary mask.
    """

    if len(claims) < 2:
        return {mode: None for mode in EVIDENCE_MODES}
    source_claim = next(
        (item for item in claims if item.get("change_type") == "remove"), claims[0]
    )
    target_claim = next(
        (item for item in claims if item.get("change_type") == "add"), claims[-1]
    )
    source = str(source_claim["entity"])
    target = str(target_claim["entity"])
    location = str(source_claim.get("location") or target_claim.get("location") or "")

    lookup_scores = [
        base._gt_entity_change_score(
            claim=item,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            visible_entities=visible_entities,
        )
        for item in claims
    ]
    gt_lookup = base._strict_mean(lookup_scores)
    oracle = base._oracle_relation_score(
        source=source,
        target=target,
        location=location,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
    )
    open_vocab_score = relation_score(
        source_masks=_open_vocab_masks(source, open_vocab),
        target_masks=_open_vocab_masks(target, open_vocab),
        location=location,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
    )
    hybrid = relation_score(
        source_masks=_routed_masks(
            source,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            visible_entities=visible_entities,
            open_vocab=open_vocab,
        ),
        target_masks=_routed_masks(
            target,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            visible_entities=visible_entities,
            open_vocab=open_vocab,
        ),
        location=location,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
    )
    return {
        "gt_class_lookup": gt_lookup,
        "open_vocab_only": open_vocab_score,
        "known_gt_unknown_ov": hybrid,
        "oracle_all_class": oracle,
    }


def _open_vocab_masks(
    entity: str,
    open_vocab: dict[str, dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray] | None:
    if entity not in open_vocab:
        return None
    values = open_vocab[entity]
    return (
        np.asarray(values["pre_mask"], dtype=bool),
        np.asarray(values["post_mask"], dtype=bool),
    )


def _routed_masks(
    entity: str,
    *,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    visible_entities: set[str],
    open_vocab: dict[str, dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray] | None:
    if entity in visible_entities and entity in class_ids:
        class_id = class_ids[entity]
        return semantic_pre == class_id, semantic_post == class_id
    return _open_vocab_masks(entity, open_vocab)


def relation_score(
    *,
    source_masks: tuple[np.ndarray, np.ndarray] | None,
    target_masks: tuple[np.ndarray, np.ndarray] | None,
    location: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
) -> float | None:
    if source_masks is None or target_masks is None:
        return None
    source_pre, source_post = source_masks
    target_pre, target_post = target_masks
    if any(
        mask.shape != semantic_pre.shape
        for mask in (source_pre, source_post, target_pre, target_post)
    ):
        return None

    source_removed = np.logical_and(
        source_pre, ~base.binary_dilate(source_post, radius=2)
    )
    target_added = np.logical_and(
        target_post, ~base.binary_dilate(target_pre, radius=2)
    )
    relation = np.logical_and(
        base.binary_dilate(source_removed, radius=3),
        base.binary_dilate(target_added, radius=3),
    )
    roi = base.location_mask(location, semantic_pre.shape)
    relation &= roi
    if not relation.any():
        return 0.0
    binary_change = np.logical_and(semantic_pre != semantic_post, roi)
    overlap = int(np.logical_and(relation, binary_change).sum())
    return float(overlap / int(relation.sum()))
