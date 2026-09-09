"""Evaluate the published ALOHa protocol on real and controlled change captions.

This adapter keeps ALOHa's official noun parser, MPNet similarity, Hungarian
matching, and minimum aggregation.  It intentionally does not add MGA's
temporal or spatial parser so that the single-image metric's blind spots remain
measurable.  ``en_core_web_sm`` can be exposed under ALOHa's hard-coded
``en_core_web_lg`` name when the larger spaCy wheel is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from aloha.metrics import ALOHa
from aloha.object_parser import SpacyObjectParser
from aloha.string_similarity import MPNetSimilarity


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values: list[float]) -> float | None:
    values = [float(value) for value in values if math.isfinite(float(value))]
    return float(np.mean(values)) if values else None


def evaluate(evaluator: ALOHa, caption: str, references: list[str]) -> tuple[float, dict]:
    score, info = evaluator(target=caption, references=references, object_detections=None)
    return float(score), info


def optimal_balanced_accuracy(labels: list[int], scores: list[float]) -> dict:
    thresholds = sorted(set(scores))
    candidates = [thresholds[0] - 1e-9, *thresholds, thresholds[-1] + 1e-9]
    best = max(
        (
            float(balanced_accuracy_score(labels, [int(score >= threshold) for score in scores])),
            float(threshold),
        )
        for threshold in candidates
    )
    return {"balanced_accuracy_oracle_threshold": best[0], "oracle_threshold": best[1]}


def real_outputs(args: argparse.Namespace, evaluator: ALOHa) -> dict:
    rows = read_jsonl(args.real_manifest)
    outputs = []
    grouped: dict[str, list[float]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        score, info = evaluate(evaluator, str(row["caption"]), [str(x) for x in row["references"]])
        grouped[str(row["model"])].append(score)
        outputs.append({
            "sample_id": row["sample_id"],
            "model": row["model"],
            "score": score,
            "target_objects": info["target_objects"],
            "reference_objects": info["reference_objects"],
            "matches": info["matches"],
        })
        if index == 1 or index % 250 == 0 or index == len(rows):
            print(f"real {index}/{len(rows)}", flush=True)
    output_path = args.output_dir / "real_output_scores.jsonl"
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
    return {
        "input": str(args.real_manifest.resolve()),
        "input_sha256": sha256(args.real_manifest),
        "rows": len(rows),
        "models": {name: {"count": len(values), "mean": mean(values)} for name, values in sorted(grouped.items())},
    }


def controlled_errors(args: argparse.Namespace, evaluator: ALOHa) -> dict:
    rows = read_jsonl(args.controlled_manifest)
    outputs = []
    labels, scores = [], []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        score, info = evaluate(evaluator, str(row["caption"]), [str(row["source_caption"])])
        label = int(bool(row["is_factually_correct"]))
        labels.append(label)
        scores.append(score)
        grouped[str(row["error_type"])].append({"score": score, "label": label})
        outputs.append({
            "item_id": row["item_id"],
            "sample_id": row["sample_id"],
            "error_type": row["error_type"],
            "is_factually_correct": bool(label),
            "score": score,
            "target_objects": info["target_objects"],
            "matches": info["matches"],
        })
        if index == 1 or index % 200 == 0 or index == len(rows):
            print(f"controlled {index}/{len(rows)}", flush=True)
    output_path = args.output_dir / "controlled_error_scores.jsonl"
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
    factual_mean = mean([score for score, label in zip(scores, labels, strict=True) if label])
    by_error = {}
    for name, values in sorted(grouped.items()):
        error_mean = mean([item["score"] for item in values])
        by_error[name] = {
            "count": len(values),
            "mean": error_mean,
            "drop_from_factual": None if factual_mean is None or error_mean is None else factual_mean - error_mean,
        }
    return {
        "input": str(args.controlled_manifest.resolve()),
        "input_sha256": sha256(args.controlled_manifest),
        "rows": len(rows),
        "positive_rows": int(sum(labels)),
        "negative_rows": int(len(labels) - sum(labels)),
        "roc_auc": float(roc_auc_score(labels, scores)),
        **optimal_balanced_accuracy(labels, scores),
        "factual_mean": factual_mean,
        "by_error_type": by_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-manifest", required=True, type=Path)
    parser.add_argument("--controlled-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    evaluator = ALOHa(
        name="aloha_spacy_mpnet",
        object_parser=SpacyObjectParser,
        similarity_measure=MPNetSimilarity,
        num_reference_examples=None,
        num_target_examples=None,
        detect_objects=False,
        similarity_aggregate_method="min",
        debug=True,
    )
    summary = {
        "protocol": "ALOHa official local variant: SpacyObjectParser + MPNetSimilarity + Hungarian/min",
        "adaptation": "Change captions are compared to text references/facts; no MGA parser, visual masks, temporal direction, or location logic is added.",
        "spaCy_model_note": "Official en_core_web_sm 3.7.1 exposed under ALOHa's hard-coded en_core_web_lg name because the 500MB lg wheel was unavailable through the current network.",
        "real_outputs": real_outputs(args, evaluator),
        "controlled_errors": controlled_errors(args, evaluator),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
