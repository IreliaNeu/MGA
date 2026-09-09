"""Summarize P0-3 minimal errors and prepare a stratified human audit sheet."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ERROR_TYPES = (
    "direction",
    "entity",
    "hallucination",
    "location",
    "no-change",
    "omission",
    "relation",
)
VISIBLE = {"building", "non-vegetated ground", "playground"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--audit-per-error", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def auc(labels: list[bool], values: list[float]) -> float | None:
    positives = [value for label, value in zip(labels, values, strict=True) if label]
    negatives = [value for label, value in zip(labels, values, strict=True) if not label]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += float(positive > negative) + 0.5 * float(positive == negative)
    return wins / (len(positives) * len(negatives))


def transition_bin(pixel_fraction: float) -> str:
    if pixel_fraction < 0.02:
        return "small_<2%"
    if pixel_fraction < 0.10:
        return "medium_2-10%"
    return "large_>=10%"


def route_group(source: str, target: str) -> str:
    visible_count = int(source in VISIBLE) + int(target in VISIBLE)
    return ("both_hidden", "mixed", "both_visible")[visible_count]


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def summarize_group(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    paired = []
    correct_scores = []
    error_scores = []
    for row in rows:
        original = finite(row["original_score"])
        error = finite(row["error_score"])
        if original is not None:
            correct_scores.append(original)
        if error is not None:
            error_scores.append(error)
        if original is not None and error is not None:
            paired.append((original, error))
    labels = [True] * len(correct_scores) + [False] * len(error_scores)
    values = correct_scores + error_scores
    true_positive = sum(value >= threshold for value in correct_scores)
    true_negative = sum(value < threshold for value in error_scores)
    true_positive_rate = true_positive / len(correct_scores) if correct_scores else None
    true_negative_rate = true_negative / len(error_scores) if error_scores else None
    balanced = (
        (true_positive_rate + true_negative_rate) / 2
        if true_positive_rate is not None and true_negative_rate is not None
        else None
    )
    return {
        "pairs": len(rows),
        "both_scored": len(paired),
        "pair_coverage": len(paired) / len(rows) if rows else None,
        "paired_accuracy": (
            sum(original > error for original, error in paired) / len(paired)
            if paired
            else None
        ),
        "tie_rate": (
            sum(original == error for original, error in paired) / len(paired)
            if paired
            else None
        ),
        "neutral_auc": auc(labels, values),
        "balanced_accuracy": balanced,
        "false_support_rate": (
            sum(value >= threshold for value in error_scores) / len(error_scores)
            if error_scores
            else None
        ),
        "unverifiable_rate": 1.0 - len(error_scores) / len(rows) if rows else None,
        "mean_original": mean(correct_scores),
        "mean_error": mean(error_scores),
    }


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {row["item_id"]: row for row in read_jsonl(args.manifest)}
    scores = read_jsonl(args.scores)
    originals = {
        row["sample_id"]: row
        for row in scores
        if row["error_type"] == "none"
    }
    enriched = []
    for row in scores:
        error_type = row["error_type"]
        if error_type not in ERROR_TYPES:
            continue
        metadata = manifest[row["item_id"]]
        transition = metadata["transition"]
        original = originals[row["sample_id"]]
        enriched.append(
            {
                **metadata,
                "error_score": row["scores"]["hybrid"]["diagnostic_score"],
                "original_score": original["scores"]["hybrid"]["diagnostic_score"],
                "hybrid_visual_confidence": row["scores"]["hybrid"]["visual_confidence"],
                "transition_bin": transition_bin(float(transition["pixel_fraction"])),
                "route_group": route_group(
                    str(transition["source_entity"]), str(transition["target_entity"])
                ),
            }
        )

    dimensions = {
        "error_type": lambda row: row["error_type"],
        "transition_size": lambda row: row["transition_bin"],
        "route_group": lambda row: row["route_group"],
        "source_entity": lambda row: row["transition"]["source_entity"],
        "target_entity": lambda row: row["transition"]["target_entity"],
        "location": lambda row: row["transition"]["location"],
    }
    strata = {}
    for dimension, getter in dimensions.items():
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in enriched:
            grouped[str(getter(row))].append(row)
        strata[dimension] = {
            key: summarize_group(group, threshold=args.threshold)
            for key, group in sorted(grouped.items())
        }

    summary = {
        "protocol": "p0-3-minimal-error-strata-v1",
        "scene_count": len({row["sample_id"] for row in enriched}),
        "error_item_count": len(enriched),
        "error_types": list(ERROR_TYPES),
        "threshold": args.threshold,
        "score": "MGA-Hybrid diagnostic_score",
        "strata": strata,
        "audit": {
            "seed": args.seed,
            "per_error_type": args.audit_per_error,
            "rows": args.audit_per_error * len(ERROR_TYPES),
            "share_of_error_items": (
                args.audit_per_error * len(ERROR_TYPES) / len(enriched)
            ),
        },
        "limitations": {
            "omission": (
                "diagnostic_score uses benchmark atomic_fact_coverage; reference-free "
                "evidence_score cannot detect unexpressed facts"
            ),
            "quantity_attribute": (
                "not generated: current SECOND fact graph and MGA claim schema do not "
                "provide independently verifiable instance-count or attribute atoms"
            ),
        },
    }
    (args.output_dir / "stratified_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rng = random.Random(args.seed)
    audit_rows = []
    for error_type in ERROR_TYPES:
        candidates = [row for row in enriched if row["error_type"] == error_type]
        candidates.sort(
            key=lambda row: (
                row["transition_bin"],
                row["route_group"],
                row["sample_id"],
            )
        )
        chosen = rng.sample(candidates, min(args.audit_per_error, len(candidates)))
        audit_rows.extend(sorted(chosen, key=lambda row: row["sample_id"]))

    fieldnames = [
        "sample_id",
        "item_id",
        "error_type",
        "source_caption",
        "perturbed_caption",
        "changed_slots",
        "source_entity",
        "target_entity",
        "location",
        "pixel_fraction",
        "transition_bin",
        "route_group",
        "mga_hybrid_original",
        "mga_hybrid_error",
        "is_single_factor_valid_0_or_1",
        "is_factually_incorrect_0_or_1",
        "is_fluent_0_or_1",
        "reviewer_notes",
    ]
    with (args.output_dir / "human_validation_140.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit_rows:
            transition = row["transition"]
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "item_id": row["item_id"],
                    "error_type": row["error_type"],
                    "source_caption": row["source_caption"],
                    "perturbed_caption": row["caption"],
                    "changed_slots": "|".join(row["changed_slots"]),
                    "source_entity": transition["source_entity"],
                    "target_entity": transition["target_entity"],
                    "location": transition["location"],
                    "pixel_fraction": transition["pixel_fraction"],
                    "transition_bin": row["transition_bin"],
                    "route_group": row["route_group"],
                    "mga_hybrid_original": row["original_score"],
                    "mga_hybrid_error": row["error_score"],
                    "is_single_factor_valid_0_or_1": "",
                    "is_factually_incorrect_0_or_1": "",
                    "is_fluent_0_or_1": "",
                    "reviewer_notes": "",
                }
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
