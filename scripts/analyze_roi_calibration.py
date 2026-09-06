"""Calibrate ROI-gated factuality thresholds on disjoint scene groups.

The predicted and feature-difference ROI scores are not probabilities and
therefore should not inherit the oracle route's fixed 0.5 decision threshold.
This script deterministically splits by ``sample_id``, chooses one threshold
per ROI route on development scenes, and reports untouched test metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from mga.evidence_routing import binary_auc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260808)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def group_split(sample_id: str, *, seed: int, dev_fraction: float) -> str:
    digest = hashlib.sha256(f"{seed}:{sample_id}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / float(2**64)
    return "dev" if value < dev_fraction else "test"


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def confusion(pairs: list[tuple[bool, float]], threshold: float) -> dict[str, float | int]:
    tp = sum(label and score >= threshold for label, score in pairs)
    fn = sum(label and score < threshold for label, score in pairs)
    fp = sum((not label) and score >= threshold for label, score in pairs)
    tn = sum((not label) and score < threshold for label, score in pairs)
    tpr = tp / (tp + fn) if tp + fn else float("nan")
    tnr = tn / (tn + fp) if tn + fp else float("nan")
    ba = (tpr + tnr) / 2 if math.isfinite(tpr) and math.isfinite(tnr) else float("nan")
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "balanced_accuracy": ba,
        "false_support_rate": fp / (fp + tn) if fp + tn else float("nan"),
        "supported_precision": tp / (tp + fp) if tp + fp else float("nan"),
    }


def threshold_candidates(pairs: list[tuple[bool, float]]) -> list[float]:
    values = sorted({score for _label, score in pairs})
    if not values:
        return []
    candidates = [math.nextafter(values[0], -math.inf)]
    candidates.extend((left + right) / 2 for left, right in zip(values, values[1:], strict=False))
    candidates.append(math.nextafter(values[-1], math.inf))
    candidates.extend(values)
    return sorted(set(candidates))


def choose_threshold(pairs: list[tuple[bool, float]]) -> tuple[float, dict[str, Any]]:
    candidates = threshold_candidates(pairs)
    if not candidates:
        raise ValueError("Development split has no finite scores")
    ranked = []
    for threshold in candidates:
        result = confusion(pairs, threshold)
        ranked.append(
            (
                -float(result["balanced_accuracy"]),
                float(result["false_support_rate"]),
                abs(threshold - 0.5),
                threshold,
                result,
            )
        )
    _neg_ba, _fsr, _distance, threshold, result = min(ranked)
    return threshold, result


def evaluate(rows: list[dict[str, Any]], method: str, threshold: float) -> dict[str, Any]:
    labeled = [
        (bool(row["is_factually_correct"]), finite(row.get("scores", {}).get(method)))
        for row in rows
    ]
    scored = [(label, score) for label, score in labeled if score is not None]
    neutral = [(label, 0.5 if score is None else score) for label, score in labeled]
    result = confusion([(label, float(score)) for label, score in scored], threshold)
    return {
        "n": len(labeled),
        "n_scored": len(scored),
        "coverage": len(scored) / len(labeled) if labeled else 0.0,
        "unverifiable_rate": 1.0 - (len(scored) / len(labeled) if labeled else 0.0),
        "conditional_auc": binary_auc([(label, float(score)) for label, score in scored]),
        "neutral_auc": binary_auc(neutral),
        **result,
    }


def main() -> None:
    args = parse_args()
    if not 0.0 < args.dev_fraction < 1.0:
        raise ValueError("--dev-fraction must be in (0, 1)")
    rows = read_jsonl(args.input)
    methods = sorted({name for row in rows for name in (row.get("scores") or {})})
    if not methods:
        raise ValueError("No row['scores'] methods found")
    splits = {
        name: [
            row
            for row in rows
            if group_split(
                str(row["sample_id"]),
                seed=args.seed,
                dev_fraction=args.dev_fraction,
            )
            == name
        ]
        for name in ("dev", "test")
    }
    output: dict[str, Any] = {
        "protocol": "group-disjoint-roi-threshold-calibration-v1",
        "input": str(args.input),
        "seed": args.seed,
        "dev_fraction": args.dev_fraction,
        "split_unit": "sample_id",
        "dev_scene_count": len({row["sample_id"] for row in splits["dev"]}),
        "test_scene_count": len({row["sample_id"] for row in splits["test"]}),
        "methods": {},
    }
    for method in methods:
        dev_pairs = [
            (bool(row["is_factually_correct"]), score)
            for row in splits["dev"]
            if (score := finite((row.get("scores") or {}).get(method))) is not None
        ]
        threshold, dev_choice = choose_threshold(dev_pairs)
        output["methods"][method] = {
            "selected_threshold": threshold,
            "selection_objective": "maximize development balanced accuracy; tie-break lower FSR",
            "dev_at_selected_threshold": {
                **evaluate(splits["dev"], method, threshold),
                "selection_confusion": dev_choice,
            },
            "test_at_selected_threshold": evaluate(splits["test"], method, threshold),
            "test_at_fixed_0_5": evaluate(splits["test"], method, 0.5),
        }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "calibration_summary.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
