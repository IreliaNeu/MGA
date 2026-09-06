"""Score a controlled minimal-error benchmark without claim-pair shortcuts.

This runner is intentionally separate from :mod:`mga.evidence_routing_v2`.
Every parsed claim is scored, an explicitly expressed source-to-target relation
is checked without falling back to a convenient remove/add pair, and omission
is measured with benchmark-only atomic fact coverage.

Two scalar views are retained:

``evidence_score``
    A reference-free conjunction of the visual support for every expressed
    claim and relation.  It cannot, by construction, detect an omitted fact.

``diagnostic_score``
    ``evidence_score * atomic_fact_coverage``.  Atomic fact coverage is derived
    only from ``base_semantics``/``transition`` in the controlled benchmark.
    It is an analysis score, not a claim that MGA detects omissions without a
    reference or semantic fact graph.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mga.evidence_routing import binary_dilate, location_mask
from mga.semantic_change import load_label_ids

MODES = ("oracle", "hybrid", "open_vocab")
ERROR_TARGET_COMPONENT = {
    "entity": "entity_support",
    "direction": "temporal_support",
    "location": "location_support",
    "relation": "relation_support",
    "hallucination": "claim_support",
    "omission": "atomic_fact_coverage",
    "no-change": "temporal_support",
}


@dataclass(frozen=True)
class RoutedMasks:
    pre: np.ndarray
    post: np.ndarray
    source: str
    pre_confidence: float | None = None
    post_confidence: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strict, component-wise scoring of minimal caption errors."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--class-map",
        required=True,
        help="JSON id-to-name mapping or a path to a JSON mapping.",
    )
    parser.add_argument(
        "--hybrid-hidden-entities",
        default="tree,low vegetation,water",
        help="Comma-separated classes routed to open-vocabulary masks in Hybrid.",
    )
    parser.add_argument("--max-scenes", type=int, default=0)
    parser.add_argument("--min-event-pixels", type=int, default=16)
    parser.add_argument("--ov-tolerance-radius", type=int, default=2)
    parser.add_argument("--relation-radius", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")


def load_class_map(value: str) -> dict[int, str]:
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.is_file() else value
    decoded = json.loads(raw)
    if "class_map" in decoded:
        decoded = decoded["class_map"]
    mapping = {int(key): str(name) for key, name in decoded.items()}
    if not mapping or len(set(mapping.values())) != len(mapping):
        raise ValueError("class map must contain unique, non-empty class names")
    return mapping


def load_open_vocab_cache(path: Path) -> dict[str, RoutedMasks]:
    if not path.is_file():
        return {}
    with np.load(path, allow_pickle=False) as value:
        required = {
            "entities_json",
            "pre_masks",
            "post_masks",
            "pre_confidences",
            "post_confidences",
        }
        missing = required - set(value.files)
        if missing:
            raise ValueError(f"{path} is missing cache arrays: {sorted(missing)}")
        entities = [str(item) for item in json.loads(str(value["entities_json"].item()))]
        pre_masks = np.asarray(value["pre_masks"], dtype=bool)
        post_masks = np.asarray(value["post_masks"], dtype=bool)
        pre_confidences = np.asarray(value["pre_confidences"], dtype=float)
        post_confidences = np.asarray(value["post_confidences"], dtype=float)
    expected = len(entities)
    if any(
        len(array) != expected
        for array in (pre_masks, post_masks, pre_confidences, post_confidences)
    ):
        raise ValueError(f"{path} has inconsistent entity and mask array lengths")
    if pre_masks.shape != post_masks.shape or pre_masks.ndim != 3:
        raise ValueError(f"{path} must contain aligned [entity,height,width] masks")
    return {
        entity: RoutedMasks(
            pre=pre_masks[index],
            post=post_masks[index],
            source="open_vocab",
            pre_confidence=float(pre_confidences[index]),
            post_confidence=float(post_confidences[index]),
        )
        for index, entity in enumerate(entities)
    }


def route_entity_masks(
    entity: str,
    *,
    mode: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    hybrid_visible_entities: set[str],
    open_vocab: dict[str, RoutedMasks],
) -> RoutedMasks | None:
    use_semantic = mode == "oracle" or (mode == "hybrid" and entity in hybrid_visible_entities)
    if use_semantic:
        class_id = class_ids.get(entity)
        if class_id is None:
            return None
        return RoutedMasks(
            pre=semantic_pre == class_id,
            post=semantic_post == class_id,
            source="semantic_gt",
            pre_confidence=1.0,
            post_confidence=1.0,
        )
    return open_vocab.get(entity)


def event_mask(
    masks: RoutedMasks,
    change_type: str,
    *,
    ov_tolerance_radius: int,
) -> np.ndarray | None:
    radius = 0 if masks.source == "semantic_gt" else ov_tolerance_radius
    pre = masks.pre
    post = masks.post
    if change_type == "add":
        return np.logical_and(post, ~binary_dilate(pre, radius=radius))
    if change_type == "remove":
        return np.logical_and(pre, ~binary_dilate(post, radius=radius))
    if change_type == "modify":
        added = np.logical_and(post, ~binary_dilate(pre, radius=radius))
        removed = np.logical_and(pre, ~binary_dilate(post, radius=radius))
        return np.logical_or(added, removed)
    return None


def capped_pixel_support(mask: np.ndarray, min_event_pixels: int) -> float:
    return min(1.0, float(np.asarray(mask, dtype=bool).sum()) / max(min_event_pixels, 1))


def score_claim(
    claim: dict[str, Any],
    *,
    mode: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    hybrid_visible_entities: set[str],
    open_vocab: dict[str, RoutedMasks],
    min_event_pixels: int,
    ov_tolerance_radius: int,
) -> dict[str, Any]:
    entity = str(claim.get("entity", "")).strip()
    change_type = str(claim.get("change_type", "unknown")).strip().lower()
    location = str(claim.get("location") or "")
    if entity == "scene" and change_type == "none":
        return score_no_change_claim(
            location=location,
            mode=mode,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            hybrid_visible_entities=hybrid_visible_entities,
            open_vocab=open_vocab,
            min_event_pixels=min_event_pixels,
            ov_tolerance_radius=ov_tolerance_radius,
        )

    routed = route_entity_masks(
        entity,
        mode=mode,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
        hybrid_visible_entities=hybrid_visible_entities,
        open_vocab=open_vocab,
    )
    common = {
        "entity": entity,
        "change_type": change_type,
        "location": location,
    }
    if routed is None:
        return {
            **common,
            "evidence_source": None,
            "entity_support": None,
            "temporal_support": None,
            "spatial_support": None,
            "location_consistency": None,
            "claim_support": None,
            "unverifiable": True,
            "reason": "entity_masks_unavailable",
        }
    if routed.pre.shape != semantic_pre.shape or routed.post.shape != semantic_pre.shape:
        return {
            **common,
            "evidence_source": routed.source,
            "entity_support": None,
            "temporal_support": None,
            "spatial_support": None,
            "location_consistency": None,
            "claim_support": None,
            "unverifiable": True,
            "reason": "mask_shape_mismatch",
        }
    event = event_mask(
        routed,
        change_type,
        ov_tolerance_radius=ov_tolerance_radius,
    )
    if event is None:
        return {
            **common,
            "evidence_source": routed.source,
            "entity_support": None,
            "temporal_support": None,
            "spatial_support": None,
            "location_consistency": None,
            "claim_support": None,
            "unverifiable": True,
            "reason": "unsupported_change_type",
        }
    if change_type == "add":
        phase_presence = routed.post
    elif change_type == "remove":
        phase_presence = routed.pre
    else:
        phase_presence = np.logical_or(routed.pre, routed.post)
    roi = location_mask(location, event.shape)
    event_pixels = int(event.sum())
    event_in_location = np.logical_and(event, roi)
    entity_support = capped_pixel_support(phase_presence, min_event_pixels)
    temporal_support = capped_pixel_support(event, min_event_pixels)
    spatial_support = capped_pixel_support(event_in_location, min_event_pixels)
    location_consistency = float(event_in_location.sum() / event_pixels) if event_pixels else 0.0
    claim_support = min(entity_support, temporal_support, spatial_support)
    return {
        **common,
        "evidence_source": routed.source,
        "pre_confidence": routed.pre_confidence,
        "post_confidence": routed.post_confidence,
        "entity_support": entity_support,
        "temporal_support": temporal_support,
        "spatial_support": spatial_support,
        "location_consistency": location_consistency,
        "claim_support": claim_support,
        "event_pixels": event_pixels,
        "event_pixels_in_location": int(event_in_location.sum()),
        "unverifiable": False,
        "reason": None,
    }


def score_no_change_claim(
    *,
    location: str,
    mode: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    hybrid_visible_entities: set[str],
    open_vocab: dict[str, RoutedMasks],
    min_event_pixels: int,
    ov_tolerance_radius: int,
) -> dict[str, Any]:
    roi = location_mask(location, semantic_pre.shape)
    if mode == "oracle":
        change = semantic_pre != semantic_post
        complete = True
        sources = ["semantic_gt"]
    else:
        change = np.zeros_like(semantic_pre, dtype=bool)
        complete = True
        sources = []
        for entity in class_ids:
            routed = route_entity_masks(
                entity,
                mode=mode,
                semantic_pre=semantic_pre,
                semantic_post=semantic_post,
                class_ids=class_ids,
                hybrid_visible_entities=hybrid_visible_entities,
                open_vocab=open_vocab,
            )
            if routed is None or routed.pre.shape != semantic_pre.shape:
                complete = False
                continue
            sources.append(routed.source)
            radius = 0 if routed.source == "semantic_gt" else ov_tolerance_radius
            added = np.logical_and(routed.post, ~binary_dilate(routed.pre, radius))
            removed = np.logical_and(routed.pre, ~binary_dilate(routed.post, radius))
            change |= np.logical_or(added, removed)
    changed_pixels = int(np.logical_and(change, roi).sum())
    # One witnessed change is sufficient to refute "no change".  Confirming it
    # requires exhaustive route coverage; otherwise the correct state is unknown.
    if changed_pixels >= min_event_pixels:
        support: float | None = 0.0
        reason = None
    elif complete:
        support = 1.0
        reason = None
    else:
        support = None
        reason = "non_exhaustive_evidence_cannot_confirm_no_change"
    return {
        "entity": "scene",
        "change_type": "none",
        "location": location,
        "evidence_source": "+".join(sorted(set(sources))) or None,
        "entity_support": support,
        "temporal_support": support,
        "spatial_support": support,
        "location_consistency": support,
        "claim_support": support,
        "event_pixels": changed_pixels,
        "event_pixels_in_location": changed_pixels,
        "unverifiable": support is None,
        "reason": reason,
    }


def expressed_relation(
    state: dict[str, Any], claims: list[dict[str, Any]]
) -> dict[str, str] | None:
    if state.get("scene_change_state") != "changed" or not state.get("included_target", True):
        return None
    source = str(state.get("source_entity", ""))
    target = str(state.get("target_entity", ""))
    direction = str(state.get("relation_direction", "source-to-target"))
    if direction == "target-to-source":
        source, target = target, source
    elif direction != "source-to-target":
        return None
    claim_atoms = {
        (str(claim.get("entity", "")), str(claim.get("change_type", ""))) for claim in claims
    }
    # The relation is validly expressed only when its directional endpoint
    # claims are present.  Never substitute a different convenient pair.
    if (source, "remove") not in claim_atoms or (target, "add") not in claim_atoms:
        return {
            "source": source,
            "target": target,
            "location": str(state.get("location") or ""),
            "invalid_endpoint_claims": "true",
        }
    return {
        "source": source,
        "target": target,
        "location": str(state.get("location") or ""),
        "invalid_endpoint_claims": "false",
    }


def score_relation(
    relation: dict[str, str] | None,
    *,
    mode: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    hybrid_visible_entities: set[str],
    open_vocab: dict[str, RoutedMasks],
    min_event_pixels: int,
    ov_tolerance_radius: int,
    relation_radius: int,
) -> dict[str, Any] | None:
    if relation is None:
        return None
    if relation["invalid_endpoint_claims"] == "true":
        return {
            **relation,
            "relation_support": 0.0,
            "location_support": 0.0,
            "relation_location_support": 0.0,
            "unverifiable": False,
            "reason": "directional_endpoint_claims_missing",
        }
    source_masks = route_entity_masks(
        relation["source"],
        mode=mode,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
        hybrid_visible_entities=hybrid_visible_entities,
        open_vocab=open_vocab,
    )
    target_masks = route_entity_masks(
        relation["target"],
        mode=mode,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
        hybrid_visible_entities=hybrid_visible_entities,
        open_vocab=open_vocab,
    )
    if source_masks is None or target_masks is None:
        return {
            **relation,
            "relation_support": None,
            "location_support": None,
            "relation_location_support": None,
            "unverifiable": True,
            "reason": "relation_endpoint_masks_unavailable",
        }
    if any(
        mask.shape != semantic_pre.shape
        for mask in (
            source_masks.pre,
            source_masks.post,
            target_masks.pre,
            target_masks.post,
        )
    ):
        return {
            **relation,
            "relation_support": None,
            "location_support": None,
            "relation_location_support": None,
            "unverifiable": True,
            "reason": "relation_mask_shape_mismatch",
        }
    if source_masks.source == target_masks.source == "semantic_gt":
        relation_mask = np.logical_and(source_masks.pre, target_masks.post)
    else:
        source_removed = event_mask(
            source_masks,
            "remove",
            ov_tolerance_radius=ov_tolerance_radius,
        )
        target_added = event_mask(
            target_masks,
            "add",
            ov_tolerance_radius=ov_tolerance_radius,
        )
        assert source_removed is not None and target_added is not None
        relation_mask = np.logical_and(
            binary_dilate(source_removed, relation_radius),
            binary_dilate(target_added, relation_radius),
        )
    roi = location_mask(relation["location"], semantic_pre.shape)
    in_location = np.logical_and(relation_mask, roi)
    relation_support = capped_pixel_support(relation_mask, min_event_pixels)
    location_support = capped_pixel_support(in_location, min_event_pixels)
    return {
        **relation,
        "source_evidence": source_masks.source,
        "target_evidence": target_masks.source,
        "relation_support": relation_support,
        "location_support": location_support,
        "relation_location_support": min(relation_support, location_support),
        "relation_pixels": int(relation_mask.sum()),
        "relation_pixels_in_location": int(in_location.sum()),
        "unverifiable": False,
        "reason": None,
    }


def _atom(kind: str, *values: str) -> str:
    return ":".join((kind, *values))


def atomic_fact_coverage(row: dict[str, Any]) -> dict[str, Any]:
    """Benchmark-only recall of semantic atoms from declared ground truth.

    Expected atoms come exclusively from ``base_semantics`` (with
    ``transition`` used only as a consistency fallback), never from the score,
    masks, or a selected claim pair.
    """

    base = dict(row.get("base_semantics") or {})
    transition = dict(row.get("transition") or {})
    source = str(base.get("source_entity") or transition.get("source_entity") or "")
    target = str(base.get("target_entity") or transition.get("target_entity") or "")
    if not source or not target:
        raise ValueError(f"{row.get('item_id')} lacks base source/target truth")
    expected = {
        _atom("claim", source, "remove"),
        _atom("claim", target, "add"),
        _atom("relation", source, target),
    }
    claims = list(row.get("claims") or [])
    represented = {
        _atom(
            "claim",
            str(claim.get("entity", "")),
            str(claim.get("change_type", "")),
        )
        for claim in claims
        if claim.get("entity") != "scene"
    }
    state = dict(row.get("perturbed_semantics") or {})
    relation = expressed_relation(state, claims)
    if relation is not None and relation["invalid_endpoint_claims"] == "false":
        represented.add(_atom("relation", relation["source"], relation["target"]))
    matched = expected & represented
    extras = represented - expected
    return {
        "coverage": len(matched) / len(expected),
        "expected": sorted(expected),
        "represented": sorted(represented),
        "matched": sorted(matched),
        "missing": sorted(expected - represented),
        "extra": sorted(extras),
    }


def strict_min(values: Iterable[float | None]) -> float | None:
    items = list(values)
    if not items or any(item is None for item in items):
        return None
    return min(float(item) for item in items if item is not None)


def mean_available(values: Iterable[float | None]) -> float | None:
    items = [float(item) for item in values if item is not None]
    return sum(items) / len(items) if items else None


def score_row(
    row: dict[str, Any],
    *,
    mode: str,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    hybrid_visible_entities: set[str],
    open_vocab: dict[str, RoutedMasks],
    min_event_pixels: int = 16,
    ov_tolerance_radius: int = 2,
    relation_radius: int = 3,
) -> dict[str, Any]:
    claims = list(row.get("claims") or [])
    claim_results = [
        score_claim(
            claim,
            mode=mode,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            hybrid_visible_entities=hybrid_visible_entities,
            open_vocab=open_vocab,
            min_event_pixels=min_event_pixels,
            ov_tolerance_radius=ov_tolerance_radius,
        )
        for claim in claims
    ]
    state = dict(row.get("perturbed_semantics") or {})
    relation_result = score_relation(
        expressed_relation(state, claims),
        mode=mode,
        semantic_pre=semantic_pre,
        semantic_post=semantic_post,
        class_ids=class_ids,
        hybrid_visible_entities=hybrid_visible_entities,
        open_vocab=open_vocab,
        min_event_pixels=min_event_pixels,
        ov_tolerance_radius=ov_tolerance_radius,
        relation_radius=relation_radius,
    )
    fact_coverage = atomic_fact_coverage(row)
    claim_support = strict_min(item["claim_support"] for item in claim_results)
    expressed_scores: list[float | None] = [claim_support]
    if relation_result is not None:
        expressed_scores.append(relation_result["relation_location_support"])
    evidence_score = strict_min(expressed_scores)
    diagnostic_score = (
        evidence_score * float(fact_coverage["coverage"]) if evidence_score is not None else None
    )

    relation_support = relation_result["relation_support"] if relation_result is not None else None
    relation_location = relation_result["location_support"] if relation_result is not None else None
    components = {
        "entity_support": mean_available(item["entity_support"] for item in claim_results),
        "temporal_support": mean_available(item["temporal_support"] for item in claim_results),
        "spatial_support": mean_available(item["spatial_support"] for item in claim_results),
        "location_support": relation_location
        if relation_location is not None
        else mean_available(item["location_consistency"] for item in claim_results),
        "relation_support": relation_support,
        "claim_support": claim_support,
        "claim_support_mean": mean_available(item["claim_support"] for item in claim_results),
        "atomic_fact_coverage": float(fact_coverage["coverage"]),
    }
    return {
        "mode": mode,
        "claim_count": len(claim_results),
        "claims": claim_results,
        "relation": relation_result,
        "atomic_facts": fact_coverage,
        "components": components,
        "evidence_score": evidence_score,
        "diagnostic_score": diagnostic_score,
        "unverifiable": diagnostic_score is None,
    }


def binary_auc(values: Iterable[tuple[bool, float]]) -> float:
    pairs = list(values)
    positives = [score for label, score in pairs if label]
    negatives = [score for label, score in pairs if not label]
    if not positives or not negatives:
        return float("nan")
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    return wins / (len(positives) * len(negatives))


def balanced_accuracy(values: Iterable[tuple[bool, float]], threshold: float) -> float:
    pairs = list(values)
    positives = [score >= threshold for label, score in pairs if label]
    negatives = [score < threshold for label, score in pairs if not label]
    if not positives or not negatives:
        return float("nan")
    return 0.5 * (sum(positives) / len(positives) + sum(negatives) / len(negatives))


MODE_DISPLAY = {
    "oracle": "MGA-GT",
    "hybrid": "MGA-Hybrid",
    "open_vocab": "MGA-OV",
}


def mode_score(row: dict[str, Any], mode: str) -> dict[str, Any]:
    scores = row.get("scores")
    if isinstance(scores, dict) and mode in scores:
        return scores[mode]
    details = row.get("score_details")
    display = MODE_DISPLAY.get(mode, mode)
    if isinstance(details, dict) and display in details:
        return details[display]
    raise KeyError(f"Missing score details for mode {mode!r}")


def independent_visual_confidence(result: dict[str, Any]) -> float | None:
    """Return mask-model confidence without reusing the factuality score."""

    values: list[float] = []
    for claim in result.get("claims") or []:
        change_type = str(claim.get("change_type") or "")
        keys = {
            "add": ("post_confidence",),
            "remove": ("pre_confidence",),
            "modify": ("pre_confidence", "post_confidence"),
        }.get(change_type, ())
        for key in keys:
            value = claim.get(key)
            if value is not None and math.isfinite(float(value)):
                values.append(float(value))
    return min(values) if values else None


def summarize_pairs(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    error_type: str,
    threshold: float,
    score_key: str = "diagnostic_score",
) -> dict[str, Any]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[str(row["sample_id"])][str(row["error_type"])] = row
    pairs = [
        (values["none"], values[error_type])
        for values in grouped.values()
        if "none" in values and error_type in values
    ]
    scored_pairs = [
        (float(mode_score(original, mode)[score_key]), float(mode_score(error, mode)[score_key]))
        for original, error in pairs
        if mode_score(original, mode)[score_key] is not None
        and mode_score(error, mode)[score_key] is not None
    ]
    neutral_values: list[tuple[bool, float]] = []
    conditional_values: list[tuple[bool, float]] = []
    for original, error in pairs:
        positive = mode_score(original, mode)[score_key]
        negative = mode_score(error, mode)[score_key]
        neutral_values.extend(
            [
                (True, 0.5 if positive is None else float(positive)),
                (False, 0.5 if negative is None else float(negative)),
            ]
        )
        if positive is not None:
            conditional_values.append((True, float(positive)))
        if negative is not None:
            conditional_values.append((False, float(negative)))
    negative_scores = [
        float(mode_score(error, mode)[score_key])
        for _, error in pairs
        if mode_score(error, mode)[score_key] is not None
    ]
    target = ERROR_TARGET_COMPONENT[error_type]
    component_pairs = []
    for original, error in pairs:
        before = mode_score(original, mode)["components"].get(target)
        after = mode_score(error, mode)["components"].get(target)
        if before is not None and after is not None:
            component_pairs.append((float(before), float(after)))
    return {
        "mode": mode,
        "error_type": error_type,
        "score": score_key,
        "n_pairs": len(pairs),
        "n_both_scored": len(scored_pairs),
        "pair_coverage": len(scored_pairs) / len(pairs) if pairs else 0.0,
        "paired_accuracy": (
            sum(original > error for original, error in scored_pairs) / len(scored_pairs)
            if scored_pairs
            else float("nan")
        ),
        "paired_tie_rate": (
            sum(original == error for original, error in scored_pairs) / len(scored_pairs)
            if scored_pairs
            else float("nan")
        ),
        "neutral_auc": binary_auc(neutral_values),
        "balanced_accuracy": balanced_accuracy(conditional_values, threshold),
        "false_support_rate": (
            sum(score >= threshold for score in negative_scores) / len(negative_scores)
            if negative_scores
            else float("nan")
        ),
        "unverifiable_rate": (
            sum(mode_score(error, mode)[score_key] is None for _, error in pairs) / len(pairs)
            if pairs
            else float("nan")
        ),
        "target_component": target,
        "target_component_n": len(component_pairs),
        "target_component_original_mean": mean_or_nan([left for left, _ in component_pairs]),
        "target_component_error_mean": mean_or_nan([right for _, right in component_pairs]),
        "target_component_delta": mean_or_nan([left - right for left, right in component_pairs]),
    }


def mean_or_nan(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def csv_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return value


def main() -> None:
    args = parse_args()
    if args.min_event_pixels < 1:
        raise ValueError("--min-event-pixels must be positive")
    class_names = load_class_map(args.class_map)
    class_ids = {name: class_id for class_id, name in class_names.items()}
    hidden = {entity.strip() for entity in args.hybrid_hidden_entities.split(",") if entity.strip()}
    unknown_hidden = hidden - set(class_ids)
    if unknown_hidden:
        raise ValueError(f"Hybrid hidden entities absent from class map: {sorted(unknown_hidden)}")
    hybrid_visible = set(class_ids) - hidden
    items = read_jsonl(args.manifest)
    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_scene[str(item["sample_id"])].append(item)
    if args.max_scenes > 0:
        allowed = set(sorted(by_scene)[: args.max_scenes])
        by_scene = {sample_id: by_scene[sample_id] for sample_id in sorted(allowed)}

    output_rows: list[dict[str, Any]] = []
    cache_missing: list[str] = []
    for index, (sample_id, scene_rows) in enumerate(sorted(by_scene.items()), start=1):
        representative = scene_rows[0]
        semantic_pre = load_label_ids(representative["pre_label"])
        semantic_post = load_label_ids(representative["post_label"])
        if semantic_pre.shape != semantic_post.shape:
            raise ValueError(f"unaligned semantic labels for {sample_id}")
        cache_path = args.cache_dir / f"{sample_id}.npz"
        open_vocab = load_open_vocab_cache(cache_path)
        if not open_vocab:
            cache_missing.append(sample_id)
        for item in scene_rows:
            scores = {
                mode: score_row(
                    item,
                    mode=mode,
                    semantic_pre=semantic_pre,
                    semantic_post=semantic_post,
                    class_ids=class_ids,
                    hybrid_visible_entities=hybrid_visible,
                    open_vocab=open_vocab,
                    min_event_pixels=args.min_event_pixels,
                    ov_tolerance_radius=args.ov_tolerance_radius,
                    relation_radius=args.relation_radius,
                )
                for mode in MODES
            }
            for detail in scores.values():
                detail["visual_confidence"] = independent_visual_confidence(detail)
            output_rows.append(
                {
                    "sample_id": sample_id,
                    "item_id": item["item_id"],
                    "error_type": item["error_type"],
                    "is_factually_correct": bool(item["is_factually_correct"]),
                    "caption": item["caption"],
                    "changed_slots": item.get("changed_slots", []),
                    "scores": scores,
                }
            )
        if index % 25 == 0 or index == len(by_scene):
            print(f"processed {index}/{len(by_scene)} scenes", flush=True)

    error_types = sorted(
        {str(row["error_type"]) for row in output_rows if row["error_type"] != "none"}
    )
    paired = [
        summarize_pairs(
            output_rows,
            mode=mode,
            error_type=error_type,
            threshold=args.threshold,
        )
        for mode in MODES
        for error_type in error_types
    ]
    # A second view exposes the reference-free limitation directly, especially
    # for omission, without changing the primary diagnostic table.
    evidence_only_pairs = [
        summarize_pairs(
            output_rows,
            mode=mode,
            error_type=error_type,
            threshold=args.threshold,
            score_key="evidence_score",
        )
        for mode in MODES
        for error_type in error_types
    ]
    summary = {
        "protocol": "minimal-error-decomposition-v1",
        "scene_count": len(by_scene),
        "item_count": len(output_rows),
        "error_types": error_types,
        "modes": list(MODES),
        "class_map": class_names,
        "hybrid_visible_entities": sorted(hybrid_visible),
        "hybrid_hidden_entities": sorted(hidden),
        "min_event_pixels": args.min_event_pixels,
        "ov_tolerance_radius": args.ov_tolerance_radius,
        "relation_radius": args.relation_radius,
        "decision_threshold": args.threshold,
        "missing_cache_scene_count": len(cache_missing),
        "missing_cache_scenes": cache_missing,
        "input_manifest": str(args.manifest),
        "input_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "cache_dir": str(args.cache_dir),
        "primary_score": "diagnostic_score",
        "score_contract": {
            "evidence_score": (
                "strict conjunction over every expressed claim and explicit relation; "
                "reference-free but cannot detect omission"
            ),
            "atomic_fact_coverage": (
                "benchmark-only recall of source-remove, target-add, and source-to-target "
                "atoms from base_semantics/transition"
            ),
            "diagnostic_score": "evidence_score * atomic_fact_coverage",
            "unverifiable": "diagnostic_score is null; neutral AUC maps null to 0.5",
        },
        "paired_diagnostic": paired,
        "paired_evidence_only": evidence_only_pairs,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "scores.jsonl", output_rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    csv_path = args.output_dir / "paired_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(paired[0]) if paired else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in paired:
            writer.writerow({key: csv_value(value) for key, value in row.items()})
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
