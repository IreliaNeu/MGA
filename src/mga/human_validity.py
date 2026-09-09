"""Held-out human validity statistics with explicit missingness and scene resampling.

Inputs contain consensus targets, not votes. Rater aggregation and adjudication
must be completed under a separately documented annotation protocol.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

import numpy as np


def _finite(value: Any) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Scores and human targets must be finite or explicitly missing")
    return number


def _ranks(values: np.ndarray) -> np.ndarray:
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return (np.cumsum(counts) - (counts - 1) / 2)[inverse]


def _rho(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2 or np.ptp(left) == 0 or np.ptp(right) == 0:
        return None
    return float(np.corrcoef(_ranks(left), _ranks(right))[0, 1])


def _tau(left: np.ndarray, right: np.ndarray) -> float | None:
    """Kendall tau-b, including ties in either variable."""
    i, j = np.triu_indices(len(left), 1)
    a, b = np.sign(left[i] - left[j]), np.sign(right[i] - right[j])
    denominator = math.sqrt(float(np.count_nonzero(a)) * float(np.count_nonzero(b)))
    return float(np.sum(a * b) / denominator) if denominator else None


def summarize(rows: list[dict], metric: str, spec: dict) -> dict:
    """Scores are oriented once; thresholds use the original score scale."""
    available = [row for row in rows if row["scores"][metric] is not None]
    direction = spec.get("direction", 1)
    x = np.asarray([direction * row["scores"][metric] for row in available], dtype=float)
    y = np.asarray([row["human_score"] for row in available], dtype=float)
    binary = [row for row in available if row["human_binary"] is not None]
    positive = sum(row["human_binary"] for row in binary)
    negative = len(binary) - positive
    auc = None
    if positive and negative:
        ranks = _ranks(np.asarray([direction * row["scores"][metric] for row in binary]))
        rank_sum = sum(
            rank for rank, row in zip(ranks, binary, strict=True) if row["human_binary"] == 1
        )
        auc = float((rank_sum - positive * (positive + 1) / 2) / (positive * negative))
    threshold = spec.get("threshold")
    bacc = fsr = None
    if threshold is not None and positive and negative:
        predictions = [direction * row["scores"][metric] >= direction * threshold for row in binary]
        tp = sum(
            pred and row["human_binary"] == 1 for pred, row in zip(predictions, binary, strict=True)
        )
        fp = sum(
            pred and row["human_binary"] == 0 for pred, row in zip(predictions, binary, strict=True)
        )
        bacc = (tp / positive + 1 - fp / negative) / 2
        fsr = fp / negative
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in available:
        groups[row["scene_id"]].append(row)
    scene_accuracies = []
    pair_count = auto_ties = human_ties = 0
    for group in groups.values():
        credits = []
        for left, right in combinations(group, 2):
            human_delta = left["human_score"] - right["human_score"]
            if human_delta == 0:
                human_ties += 1
                continue
            delta = direction * (left["scores"][metric] - right["scores"][metric])
            credit = 0.5 if delta == 0 else float(delta * human_delta > 0)
            auto_ties += int(delta == 0)
            pair_count += 1
            credits.append(credit)
        if credits:
            scene_accuracies.append(float(np.mean(credits)))
    return {
        "n_target": len(rows),
        "n_scored": len(available),
        "scene_count": len({row["scene_id"] for row in available}),
        "evaluation_coverage": len(available) / len(rows) if rows else None,
        "n_unavailable": len(rows) - len(available),
        "n_binary": len(binary),
        "positive": positive,
        "negative": negative,
        "roc_auc": auc,
        "balanced_accuracy": bacc,
        "false_support_rate": fsr,
        "spearman_rho": _rho(y, x),
        "kendall_tau_b": _tau(y, x),
        "pairwise_accuracy_scene_macro": (
            float(np.mean(scene_accuracies)) if scene_accuracies else None
        ),
        "pairwise_scenes": len(scene_accuracies),
        "pairwise_pairs": pair_count,
        "automatic_pair_ties": auto_ties,
        "human_pair_ties_excluded": human_ties,
    }


def validate_rows(rows: list[dict], metrics: dict, split: str) -> list[dict]:
    if not metrics:
        raise ValueError("At least one metric specification is required")
    for name, spec in metrics.items():
        if spec.get("direction", 1) not in (-1, 1):
            raise ValueError(f"Invalid direction for {name}")
        if spec.get("threshold") is not None:
            _finite(spec["threshold"])
    seen = set()
    scene_splits: dict[str, str] = {}
    item_identity: dict[str, tuple[str, str]] = {}
    selected = []
    for original in rows:
        row = dict(original)
        for field in ("scene_id", "item_id", "dimension", "split", "caption_sha256"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Missing or invalid {field}")
        if row["split"] not in {"dev", "test", "pilot", "training"}:
            raise ValueError("Unknown split")
        digest = row["caption_sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("caption_sha256 must be a lowercase SHA-256 digest")
        key = (row["item_id"], row["dimension"])
        if key in seen:
            raise ValueError(f"Duplicate item/dimension: {key}")
        seen.add(key)
        identity = (row["scene_id"], digest)
        if item_identity.setdefault(row["item_id"], identity) != identity:
            raise ValueError("Item caption or scene changes across dimensions")
        if scene_splits.setdefault(row["scene_id"], row["split"]) != row["split"]:
            raise ValueError("Scene leakage across splits")
        if row.get("human_status") not in {"rated", "unverifiable", "not_applicable"}:
            raise ValueError("human_status must be rated, unverifiable, or not_applicable")
        row["human_score"] = _finite(row.get("human_score"))
        row["human_binary"] = _finite(row.get("human_binary"))
        if row["human_binary"] not in (None, 0, 1):
            raise ValueError("human_binary must be 0, 1, or null; do not infer a cutoff")
        if row["human_status"] == "rated" and row["human_score"] is None:
            raise ValueError("Rated items require a human_score")
        if row["human_status"] != "rated" and (
            row["human_score"] is not None or row["human_binary"] is not None
        ):
            raise ValueError("Unverifiable/not-applicable human targets must remain null")
        if not isinstance(row.get("scores"), dict) or set(row["scores"]) != set(metrics):
            raise ValueError("Each item must name every configured metric; use null if unavailable")
        row["scores"] = {name: _finite(value) for name, value in row["scores"].items()}
        if row["split"] == split:
            selected.append(row)
    if not selected:
        raise ValueError(f"No items in requested split {split}")
    return selected


STATISTICS = (
    "roc_auc",
    "balanced_accuracy",
    "false_support_rate",
    "spearman_rho",
    "kendall_tau_b",
    "pairwise_accuracy_scene_macro",
)


def _interval(values: list[float], replicates: int) -> dict:
    return {
        "percentile_95ci": np.quantile(values, [0.025, 0.975]).tolist() if values else None,
        "valid_replicates": len(values),
        "requested_replicates": replicates,
    }


def rater_agreement(votes: list[dict], consensus: list[dict], *, split: str) -> dict:
    """Nominal Krippendorff alpha on pre-adjudication votes, allowing missingness.

    `unverifiable` is a category; `not_applicable` and blank are excluded.
    Numeric scales are treated nominally here, without assuming interval spacing.
    """
    index = {(row["item_id"], row["dimension"]): row for row in consensus}
    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    seen = set()
    for vote in votes:
        key = (vote["item_id"], vote["dimension"])
        target = index.get(key)
        if target is None:
            raise ValueError("Vote has no matching consensus item/dimension")
        if any(vote.get(field) != target[field] for field in ("scene_id", "caption_sha256")):
            raise ValueError("Vote caption/scene does not match consensus")
        rater = vote.get("rater_id")
        if not isinstance(rater, str) or not rater.strip():
            raise ValueError("Vote requires a rater_id")
        unique = (*key, rater)
        if unique in seen:
            raise ValueError("Duplicate vote from the same rater")
        seen.add(unique)
        if target["split"] != split:
            continue
        rating = vote.get("rating")
        if rating in (None, "", "not_applicable"):
            continue
        label = "unverifiable" if rating == "unverifiable" else str(_finite(rating))
        grouped[vote["dimension"]][vote["item_id"]].append(label)
    output = {}
    for dimension in sorted({row["dimension"] for row in consensus if row["split"] == split}):
        units = [values for values in grouped[dimension].values() if len(values) >= 2]
        counts = Counter(value for unit in units for value in unit)
        n = sum(counts.values())
        disagreement = sum(
            (len(unit) ** 2 - sum(count**2 for count in Counter(unit).values())) / (len(unit) - 1)
            for unit in units
        )
        observed = disagreement / n if n else None
        expected = (
            (n**2 - sum(count**2 for count in counts.values())) / (n * (n - 1)) if n > 1 else None
        )
        output[dimension] = {
            "krippendorff_alpha_nominal": 1 - observed / expected if expected else None,
            "units_with_at_least_two_votes": len(units),
            "usable_votes": n,
            "unanimous_unit_fraction": sum(len(set(unit)) == 1 for unit in units) / len(units)
            if units
            else None,
            "category_counts": dict(counts),
            "scale": "nominal; includes unverifiable, excludes not_applicable and missing",
            "stage": "pre-adjudication votes supplied by caller",
        }
    return output


def analyze(
    rows: list[dict],
    metrics: dict,
    *,
    split: str = "test",
    replicates: int = 2000,
    seed: int = 20260907,
) -> dict:
    """Report per-metric coverage and paired comparisons on common support.

    Bootstrap copies get distinct scene IDs, so repeated draws cannot create
    artificial candidate pairs between two copies of the same scene.
    """
    if replicates < 1:
        raise ValueError("replicates must be positive")
    selected = validate_rows(rows, metrics, split)
    output: dict[str, Any] = {
        "protocol": "heldout-human-validity-consensus-v1",
        "split": split,
        "seed": seed,
        "bootstrap_unit": "scene",
        "replicates": replicates,
        "threshold_selection": "none; supplied thresholds must be frozen before test",
        "missing_auto_policy": "conditional statistics plus explicit availability counts",
        "human_ties": "excluded from candidate pair comparisons; auto ties receive 0.5",
        "metric_specifications": metrics,
        "dimensions": {},
    }
    for dimension in sorted({row["dimension"] for row in selected}):
        group = [row for row in selected if row["dimension"] == dimension]
        rated = [row for row in group if row["human_status"] == "rated"]
        result = {
            "human_status_counts": {
                status: sum(row["human_status"] == status for row in group)
                for status in ("rated", "unverifiable", "not_applicable")
            },
            "per_metric_available": {
                name: summarize(rated, name, spec) for name, spec in metrics.items()
            },
        }
        # Same eligible human targets AND same metric support for every comparison.
        common = [
            row for row in rated if all(value is not None for value in row["scores"].values())
        ]
        point = {name: summarize(common, name, spec) for name, spec in metrics.items()}
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in common:
            groups[row["scene_id"]].append(row)
        scenes = sorted(groups)
        estimates = {name: {stat: [] for stat in STATISTICS} for name in metrics}
        pairs = list(combinations(metrics, 2))
        differences = {
            f"{left}_minus_{right}": {stat: [] for stat in STATISTICS} for left, right in pairs
        }
        rng = np.random.default_rng(seed)
        # A single cluster cannot estimate between-scene sampling uncertainty.
        for _ in range(replicates if len(scenes) >= 2 else 0):
            sample = [
                dict(row, scene_id=f"draw_{copy}")
                for copy, index in enumerate(rng.integers(len(scenes), size=len(scenes)))
                for row in groups[scenes[int(index)]]
            ]
            values = {name: summarize(sample, name, spec) for name, spec in metrics.items()}
            for name in metrics:
                for stat in STATISTICS:
                    if values[name][stat] is not None:
                        estimates[name][stat].append(values[name][stat])
            for left, right in pairs:
                for stat in STATISTICS:
                    a, b = values[left][stat], values[right][stat]
                    if a is not None and b is not None:
                        differences[f"{left}_minus_{right}"][stat].append(a - b)
        result["common_support"] = {
            "n": len(common),
            "scene_count": len(scenes),
            "point_estimates": point,
            "bootstrap": {
                name: {stat: _interval(values, replicates) for stat, values in stats.items()}
                for name, stats in estimates.items()
            },
            "paired_differences": {
                f"{left}_minus_{right}": {
                    stat: {
                        "point": point[left][stat] - point[right][stat]
                        if point[left][stat] is not None and point[right][stat] is not None
                        else None,
                        **_interval(differences[f"{left}_minus_{right}"][stat], replicates),
                    }
                    for stat in STATISTICS
                }
                for left, right in pairs
            },
        }
        output["dimensions"][dimension] = result
    return output
