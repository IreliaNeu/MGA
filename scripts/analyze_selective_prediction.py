"""Analyze binary selective prediction for MGA-style factuality scores.

Rows must contain an independent binary ground-truth label.  Scores may be a
``scores`` mapping (the semantic-change experiment format), or methods can be
declared explicitly with ``--method NAME=dot.path``.  Missing scores are
treated as explicit abstentions and never silently replaced by a model label.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_TARGET_COVERAGES = (0.10, 0.25, 0.50, 0.75, 1.00)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label-field", default="is_factually_correct")
    parser.add_argument("--id-field", default="item_id")
    parser.add_argument("--group-field", default="sample_id")
    parser.add_argument(
        "--method",
        action="append",
        default=[],
        metavar="NAME=DOT.PATH",
        help="Repeat for explicit methods; otherwise auto-detect row['scores'].",
    )
    parser.add_argument(
        "--confidence-path",
        action="append",
        default=[],
        metavar="NAME=DOT.PATH",
        help="Optional independent confidence; default is distance from threshold.",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument(
        "--target-coverages",
        default=",".join(str(value) for value in DEFAULT_TARGET_COVERAGES),
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def parse_assignments(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Expected NAME=DOT.PATH, got {value!r}")
        name, path = value.split("=", 1)
        if not name.strip() or not path.strip():
            raise ValueError(f"Expected NAME=DOT.PATH, got {value!r}")
        result[name.strip()] = path.strip()
    return result


def infer_methods(rows: list[dict[str, Any]]) -> dict[str, str]:
    names = sorted({str(name) for row in rows for name in (row.get("scores") or {})})
    if names:
        return {name: f"scores.{name}" for name in names}
    if any(isinstance(row.get("score"), dict) for row in rows):
        return {"MGA-Overall": "score.overall"}
    raise ValueError("Could not infer score methods. Supply --method NAME=DOT.PATH.")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "supported", "correct"}:
            return True
        if normalized in {"0", "false", "no", "contradicted", "incorrect"}:
            return False
    raise ValueError(f"Not a binary label: {value!r}")


def finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def prepare_entries(
    rows: list[dict[str, Any]],
    *,
    method_paths: dict[str, str],
    confidence_paths: dict[str, str],
    label_field: str,
    id_field: str,
    group_field: str,
    threshold: float,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        label_value = get_path(row, label_field)
        if label_value is None:
            raise ValueError(f"Row {index} is missing label field {label_field!r}")
        label = parse_bool(label_value)
        item_id = str(get_path(row, id_field) or row.get("sample_id") or index)
        group_id = str(get_path(row, group_field) or row.get("sample_id") or item_id)
        for method, score_path in method_paths.items():
            score = finite_float(get_path(row, score_path))
            confidence = None
            if score is not None:
                confidence_path = confidence_paths.get(method)
                confidence = (
                    finite_float(get_path(row, confidence_path)) if confidence_path else None
                )
                if confidence is None:
                    confidence = abs(score - threshold)
            result[method].append(
                {
                    "item_id": item_id,
                    "group_id": group_id,
                    "label": label,
                    "score": score,
                    "confidence": confidence,
                }
            )
    return dict(result)


def selected_metrics(
    selected: list[dict[str, Any]], *, threshold: float
) -> dict[str, float | int | None]:
    if not selected:
        return {
            "selected_count": 0,
            "risk": None,
            "accuracy": None,
            "false_support_rate": None,
            "supported_precision": None,
            "predicted_supported_count": 0,
        }
    decisions = [float(item["score"]) >= threshold for item in selected]
    labels = [bool(item["label"]) for item in selected]
    errors = sum(predicted != label for predicted, label in zip(decisions, labels, strict=False))
    negatives = [
        predicted for predicted, label in zip(decisions, labels, strict=False) if not label
    ]
    predicted_supported = [
        label for predicted, label in zip(decisions, labels, strict=False) if predicted
    ]
    risk = errors / len(selected)
    return {
        "selected_count": len(selected),
        "risk": risk,
        "accuracy": 1.0 - risk,
        "false_support_rate": (sum(negatives) / len(negatives) if negatives else None),
        "supported_precision": (
            sum(predicted_supported) / len(predicted_supported) if predicted_supported else None
        ),
        "predicted_supported_count": len(predicted_supported),
    }


def risk_coverage_analysis(
    entries: list[dict[str, Any]],
    *,
    threshold: float = 0.5,
    target_coverages: tuple[float, ...] = DEFAULT_TARGET_COVERAGES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    total = len(entries)
    scored = [entry for entry in entries if entry["score"] is not None]
    scored.sort(key=lambda row: (-float(row["confidence"]), row["item_id"]))
    curve: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    index = 0
    while index < len(scored):
        confidence = float(scored[index]["confidence"])
        end = index + 1
        while end < len(scored) and math.isclose(
            float(scored[end]["confidence"]), confidence, rel_tol=0.0, abs_tol=1e-12
        ):
            end += 1
        selected.extend(scored[index:end])
        metrics = selected_metrics(selected, threshold=threshold)
        curve.append(
            {
                "coverage": len(selected) / total if total else 0.0,
                "conditional_coverage": len(selected) / len(scored) if scored else 0.0,
                "confidence_threshold": confidence,
                **metrics,
            }
        )
        index = end

    # Right-continuous rectangular integration over the observable coverage range.
    previous_coverage = 0.0
    aurc_total_axis = 0.0
    for point in curve:
        coverage = float(point["coverage"])
        risk = float(point["risk"])
        aurc_total_axis += (coverage - previous_coverage) * risk
        previous_coverage = coverage
    max_coverage = len(scored) / total if total else 0.0
    target_points = []
    for target in target_coverages:
        point = next(
            (candidate for candidate in curve if candidate["coverage"] >= target),
            None,
        )
        if point is None:
            target_points.append(
                {
                    "target_coverage": target,
                    "attainable": False,
                    "reason": "explicit_abstentions_limit_maximum_coverage",
                }
            )
        else:
            target_points.append(
                {
                    "target_coverage": target,
                    "attainable": True,
                    **point,
                }
            )
    full_metrics = selected_metrics(scored, threshold=threshold)
    summary = {
        "n": total,
        "n_scored": len(scored),
        "evaluation_coverage": max_coverage,
        "explicit_abstention_rate": 1.0 - max_coverage,
        "threshold": threshold,
        "confidence_definition": (
            "provided confidence when configured; otherwise absolute distance "
            "between the factuality score and the decision threshold"
        ),
        "tie_policy": "include all items sharing the boundary confidence",
        "aurc": aurc_total_axis / max_coverage if max_coverage > 0 else None,
        "aurc_total_axis": aurc_total_axis,
        "aurc_definition": (
            "right-continuous area under selective risk over scored coverage; "
            "aurc is normalized by maximum attainable coverage"
        ),
        "full_scored_set": full_metrics,
        "target_coverages": target_points,
    }
    return summary, curve


def main() -> None:
    args = parse_args()
    rows = read_jsonl(args.input)
    method_paths = parse_assignments(args.method) if args.method else infer_methods(rows)
    confidence_paths = parse_assignments(args.confidence_path)
    unknown_confidence = sorted(set(confidence_paths) - set(method_paths))
    if unknown_confidence:
        raise ValueError(
            "Confidence paths declared for unknown methods: " + ", ".join(unknown_confidence)
        )
    target_coverages = tuple(
        float(value.strip()) for value in args.target_coverages.split(",") if value.strip()
    )
    if not target_coverages or any(value <= 0 or value > 1 for value in target_coverages):
        raise ValueError("Target coverages must be in (0, 1].")
    by_method = prepare_entries(
        rows,
        method_paths=method_paths,
        confidence_paths=confidence_paths,
        label_field=args.label_field,
        id_field=args.id_field,
        group_field=args.group_field,
        threshold=args.threshold,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    curve_rows = []
    for method, entries in sorted(by_method.items()):
        summary, curve = risk_coverage_analysis(
            entries,
            threshold=args.threshold,
            target_coverages=target_coverages,
        )
        summaries[method] = summary
        curve_rows.extend({"method": method, **point} for point in curve)
    output = {
        "protocol": "binary-selective-prediction-v1",
        "input": str(args.input),
        "label_field": args.label_field,
        "method_paths": method_paths,
        "confidence_paths": confidence_paths,
        "metric_notes": {
            "risk": "misclassification rate among retained predictions",
            "false_support_rate": "false supported decisions divided by retained negatives",
            "supported_precision": "correct supported decisions divided by retained supported decisions",  # noqa: E501
            "explicit_abstention": "missing/non-finite score; never inferred from the prediction",
        },
        "methods": summaries,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    with (args.output_dir / "risk_coverage.jsonl").open("w", encoding="utf-8") as handle:
        for row in curve_rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
