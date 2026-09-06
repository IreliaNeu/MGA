"""Four evidence routes for closed-set and open-vocabulary change claims."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

EVIDENCE_MODES = (
    "gt_class_lookup",
    "open_vocab_only",
    "known_gt_unknown_ov",
    "oracle_all_class",
)


def score_evidence_modes(
    *,
    claims: list[dict[str, Any]],
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    visible_entities: set[str],
    open_vocab: dict[str, dict[str, Any]],
) -> dict[str, float | None]:
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
        _gt_entity_change_score(
            claim=item,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            visible_entities=visible_entities,
        )
        for item in claims
    ]
    gt_lookup = _strict_mean(lookup_scores)
    oracle = _oracle_relation_score(
        source=source,
        target=target,
        location=location,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
    )
    open_vocab_score = _open_vocab_relation_score(
        source=source,
        target=target,
        location=location,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        open_vocab=open_vocab,
    )
    hybrid = (
        oracle
        if source in visible_entities and target in visible_entities
        else open_vocab_score
    )
    return {
        "gt_class_lookup": gt_lookup,
        "open_vocab_only": open_vocab_score,
        "known_gt_unknown_ov": hybrid,
        "oracle_all_class": oracle,
    }


def grounder_diagnostics(
    *,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    open_vocab: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    diagnostics = []
    for entity, values in sorted(open_vocab.items()):
        if entity not in class_ids:
            continue
        class_id = class_ids[entity]
        predicted_pre = np.asarray(values["pre_mask"], dtype=bool)
        predicted_post = np.asarray(values["post_mask"], dtype=bool)
        target_pre = semantic_pre == class_id
        target_post = semantic_post == class_id
        target_add = np.logical_and(~target_pre, target_post)
        target_remove = np.logical_and(target_pre, ~target_post)
        predicted_add = np.logical_and(
            predicted_post, ~binary_dilate(predicted_pre, radius=2)
        )
        predicted_remove = np.logical_and(
            predicted_pre, ~binary_dilate(predicted_post, radius=2)
        )
        diagnostics.append(
            {
                "entity": entity,
                "pre_iou": mask_iou(predicted_pre, target_pre),
                "post_iou": mask_iou(predicted_post, target_post),
                "add_iou": mask_iou(predicted_add, target_add),
                "remove_iou": mask_iou(predicted_remove, target_remove),
                "pre_confidence": float(values.get("pre_confidence", 0.0)),
                "post_confidence": float(values.get("post_confidence", 0.0)),
                "pre_fraction": float(predicted_pre.mean()),
                "post_fraction": float(predicted_post.mean()),
            }
        )
    return diagnostics


def summarize_scores(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    summary = {}
    for mode in EVIDENCE_MODES:
        values = [
            (bool(row["is_factually_correct"]), row["scores"].get(mode))
            for row in rows
        ]
        available = [(label, float(score)) for label, score in values if score is not None]
        neutral = [(label, 0.5 if score is None else float(score)) for label, score in values]
        positives = [score for label, score in available if label]
        negatives = [score for label, score in available if not label]
        summary[mode] = {
            "n": len(values),
            "n_scored": len(available),
            "coverage": len(available) / len(values) if values else 0.0,
            "conditional_auc": binary_auc(available),
            "neutral_auc": binary_auc(neutral),
            "balanced_accuracy": balanced_accuracy(available),
            "positive_mean": mean_or_nan(positives),
            "negative_mean": mean_or_nan(negatives),
            "false_support_rate": (
                sum(score >= 0.5 for score in negatives) / len(negatives)
                if negatives
                else float("nan")
            ),
        }
    return summary


def _gt_entity_change_score(
    *,
    claim: dict[str, Any],
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    visible_entities: set[str],
) -> float | None:
    entity = str(claim["entity"])
    if entity not in visible_entities or entity not in class_ids:
        return None
    class_id = class_ids[entity]
    pre = semantic_pre == class_id
    post = semantic_post == class_id
    change_type = str(claim.get("change_type", "unknown"))
    if change_type == "add":
        mask = np.logical_and(~pre, post)
    elif change_type == "remove":
        mask = np.logical_and(pre, ~post)
    elif change_type == "modify":
        mask = np.logical_xor(pre, post)
    else:
        return None
    return float(mask.any())


def _oracle_relation_score(
    *,
    source: str,
    target: str,
    location: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
) -> float | None:
    if source not in class_ids or target not in class_ids:
        return None
    relation = np.logical_and(
        semantic_pre == class_ids[source],
        semantic_post == class_ids[target],
    )
    relation &= location_mask(location, relation.shape)
    return float(relation.any())


def _open_vocab_relation_score(
    *,
    source: str,
    target: str,
    location: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    open_vocab: dict[str, dict[str, Any]],
) -> float | None:
    if source not in open_vocab or target not in open_vocab:
        return None
    source_values = open_vocab[source]
    target_values = open_vocab[target]
    source_pre = np.asarray(source_values["pre_mask"], dtype=bool)
    source_post = np.asarray(source_values["post_mask"], dtype=bool)
    target_pre = np.asarray(target_values["pre_mask"], dtype=bool)
    target_post = np.asarray(target_values["post_mask"], dtype=bool)
    if any(
        mask.shape != semantic_pre.shape
        for mask in (source_pre, source_post, target_pre, target_post)
    ):
        return None

    source_removed = np.logical_and(
        source_pre, ~binary_dilate(source_post, radius=2)
    )
    target_added = np.logical_and(
        target_post, ~binary_dilate(target_pre, radius=2)
    )
    relation = np.logical_and(
        binary_dilate(source_removed, radius=3),
        binary_dilate(target_added, radius=3),
    )
    roi = location_mask(location, semantic_pre.shape)
    relation &= roi
    if not relation.any():
        return None
    change = np.logical_and(semantic_pre != semantic_post, roi)
    overlap = int(np.logical_and(relation, change).sum())
    precision = overlap / int(relation.sum())
    return float(precision)


def location_mask(location: str, shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    mask = np.zeros(shape, dtype=bool)
    if not location:
        mask[:] = True
        return mask
    if location == "center":
        mask[height // 3 : (2 * height) // 3, width // 3 : (2 * width) // 3] = True
        return mask
    vertical = slice(0, height // 2) if "upper" in location else slice(height // 2, height)
    horizontal = slice(0, width // 2) if "left" in location else slice(width // 2, width)
    mask[vertical, horizontal] = True
    return mask


def binary_dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    value = np.asarray(mask, dtype=bool)
    if radius <= 0:
        return value.copy()
    padded = np.pad(value, radius, mode="constant")
    result = np.zeros_like(value)
    height, width = value.shape
    for y_offset in range(2 * radius + 1):
        for x_offset in range(2 * radius + 1):
            result |= padded[
                y_offset : y_offset + height,
                x_offset : x_offset + width,
            ]
    return result


def mask_iou(left: np.ndarray, right: np.ndarray) -> float | None:
    union = np.logical_or(left, right)
    if not union.any():
        return None
    return float(np.logical_and(left, right).sum() / union.sum())


def binary_auc(values: Iterable[tuple[bool, float]]) -> float:
    pairs = list(values)
    positives = [score for label, score in pairs if label]
    negatives = [score for label, score in pairs if not label]
    if not positives or not negatives:
        return float("nan")
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def balanced_accuracy(values: Iterable[tuple[bool, float]]) -> float:
    pairs = list(values)
    positives = [score >= 0.5 for label, score in pairs if label]
    negatives = [score < 0.5 for label, score in pairs if not label]
    if not positives or not negatives:
        return float("nan")
    return 0.5 * (
        sum(positives) / len(positives) + sum(negatives) / len(negatives)
    )


def mean_or_nan(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _strict_mean(values: list[float | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return min(float(value) for value in values if value is not None)
