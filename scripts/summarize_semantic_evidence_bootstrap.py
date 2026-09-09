"""Scene-level bootstrap confidence intervals for the four evidence routes."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from mga.evidence_routing import EVIDENCE_MODES, summarize_scores

METRICS = (
    "coverage",
    "neutral_auc",
    "balanced_accuracy",
    "false_support_rate",
)
PAIRS = (
    ("known_gt_unknown_ov", "gt_class_lookup"),
    ("known_gt_unknown_ov", "open_vocab_only"),
    ("oracle_all_class", "known_gt_unknown_ov"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260726)
    args = parser.parse_args()

    report = {
        "iterations": args.iterations,
        "seed": args.seed,
        "resampling_unit": "scene",
        "conditions": {},
    }
    for condition in ("closed_set", "hidden_class"):
        rows = read_jsonl(args.run_dir / f"{condition}_scores.jsonl")
        report["conditions"][condition] = bootstrap(
            rows,
            iterations=args.iterations,
            seed=args.seed,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=True))


def bootstrap(rows: list[dict], *, iterations: int, seed: int) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["sample_id"])].append(row)
    scene_ids = sorted(grouped)
    point = summarize_scores(rows)
    distributions = {
        mode: {metric: [] for metric in METRICS} for mode in EVIDENCE_MODES
    }
    pair_distributions = {
        f"{left}_minus_{right}": {metric: [] for metric in METRICS}
        for left, right in PAIRS
    }
    rng = np.random.default_rng(seed)
    for _ in range(iterations):
        sampled = rng.choice(scene_ids, size=len(scene_ids), replace=True)
        boot_rows = [
            row
            for synthetic_index, sample_id in enumerate(sampled)
            for row in _renamed_rows(grouped[str(sample_id)], synthetic_index)
        ]
        summary = summarize_scores(boot_rows)
        for mode in EVIDENCE_MODES:
            for metric in METRICS:
                value = float(summary[mode][metric])
                if math.isfinite(value):
                    distributions[mode][metric].append(value)
        for left, right in PAIRS:
            pair_key = f"{left}_minus_{right}"
            for metric in METRICS:
                left_value = float(summary[left][metric])
                right_value = float(summary[right][metric])
                if math.isfinite(left_value) and math.isfinite(right_value):
                    pair_distributions[pair_key][metric].append(
                        left_value - right_value
                    )

    intervals = {
        mode: {
            metric: interval(distributions[mode][metric])
            for metric in METRICS
        }
        for mode in EVIDENCE_MODES
    }
    pairwise = {}
    for left, right in PAIRS:
        key = f"{left}_minus_{right}"
        pairwise[key] = {}
        for metric in METRICS:
            values = pair_distributions[key][metric]
            point_delta = float(point[left][metric]) - float(point[right][metric])
            pairwise[key][metric] = {
                "point_delta": point_delta,
                **interval(values),
            }
    return {
        "scene_count": len(scene_ids),
        "item_count": len(rows),
        "point": point,
        "confidence_intervals": intervals,
        "paired_deltas": pairwise,
    }


def _renamed_rows(rows: list[dict], synthetic_index: int) -> list[dict]:
    return [
        {**row, "sample_id": f"bootstrap_{synthetic_index:06d}"}
        for row in rows
    ]


def interval(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n_bootstrap": 0, "low": float("nan"), "high": float("nan")}
    return {
        "n_bootstrap": len(values),
        "low": float(np.quantile(values, 0.025)),
        "high": float(np.quantile(values, 0.975)),
    }


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    main()
