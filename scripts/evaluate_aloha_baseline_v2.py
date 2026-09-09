"""Run ALOHa with its official local parser and a pre-cached MPNet snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import spacy
from sentence_transformers import SentenceTransformer
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from aloha.metrics import ALOHa
from aloha.object_parser import SpacyObjectParser
from aloha.string_similarity import MPNetSimilarity


class LocalMPNetSimilarity(MPNetSimilarity):
    def __init__(self) -> None:
        self._model = SentenceTransformer("/root/mga-external/models/all-mpnet-base-v2")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values: list[float]) -> float | None:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    return float(np.mean(clean)) if clean else None


def score(evaluator: ALOHa, caption: str, references: list[str]) -> tuple[float, dict]:
    value, info = evaluator(target=caption, references=references, object_detections=None)
    return float(value), info


def best_balanced_accuracy(labels: list[int], scores: list[float]) -> dict:
    thresholds = sorted(set(scores))
    candidates = [thresholds[0] - 1e-9, *thresholds, thresholds[-1] + 1e-9]
    value, threshold = max(
        (float(balanced_accuracy_score(labels, [int(x >= t) for x in scores])), float(t))
        for t in candidates
    )
    return {"balanced_accuracy_oracle_threshold": value, "oracle_threshold": threshold}


def eval_real(evaluator: ALOHa, path: Path, output_dir: Path) -> dict:
    rows = read_jsonl(path)
    output, grouped = [], defaultdict(list)
    for index, row in enumerate(rows, 1):
        value, info = score(evaluator, str(row["caption"]), [str(x) for x in row["references"]])
        grouped[str(row["model"])].append(value)
        output.append({
            "sample_id": row["sample_id"], "model": row["model"], "score": value,
            "target_objects": info["target_objects"], "matches": info["matches"],
        })
        if index == 1 or index % 250 == 0 or index == len(rows):
            print(f"real {index}/{len(rows)}", flush=True)
    (output_dir / "real_output_scores.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8"
    )
    return {"input": str(path.resolve()), "input_sha256": sha256(path), "rows": len(rows),
            "models": {name: {"count": len(vals), "mean": mean(vals)} for name, vals in sorted(grouped.items())}}


def eval_controlled(evaluator: ALOHa, path: Path, output_dir: Path) -> dict:
    rows = read_jsonl(path)
    output, labels, scores, grouped = [], [], [], defaultdict(list)
    for index, row in enumerate(rows, 1):
        value, info = score(evaluator, str(row["caption"]), [str(row["source_caption"])])
        label, error = int(bool(row["is_factually_correct"])), str(row["error_type"])
        labels.append(label); scores.append(value); grouped[error].append(value)
        output.append({"item_id": row["item_id"], "sample_id": row["sample_id"],
                       "error_type": error, "is_factually_correct": bool(label), "score": value,
                       "target_objects": info["target_objects"], "matches": info["matches"]})
        if index == 1 or index % 200 == 0 or index == len(rows):
            print(f"controlled {index}/{len(rows)}", flush=True)
    (output_dir / "controlled_error_scores.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8"
    )
    factual = mean([value for value, label in zip(scores, labels, strict=True) if label])
    by_error = {}
    for name, vals in sorted(grouped.items()):
        value = mean(vals)
        by_error[name] = {"count": len(vals), "mean": value,
                          "drop_from_factual": None if factual is None or value is None else factual - value}
    return {"input": str(path.resolve()), "input_sha256": sha256(path), "rows": len(rows),
            "positive_rows": sum(labels), "negative_rows": len(labels) - sum(labels),
            "roc_auc": float(roc_auc_score(labels, scores)), **best_balanced_accuracy(labels, scores),
            "factual_mean": factual, "by_error_type": by_error}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-manifest", required=True, type=Path)
    parser.add_argument("--controlled-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    evaluator = ALOHa(name="aloha_spacy_mpnet", object_parser=SpacyObjectParser,
                      similarity_measure=LocalMPNetSimilarity, detect_objects=False,
                      similarity_aggregate_method="min", debug=True)
    # The official small English pipeline preserves the POS/dependency parser
    # interfaces used by ALOHa while avoiding the unavailable 500MB lg wheel.
    evaluator._object_parser._model = spacy.load("en_core_web_sm")
    evaluator._nlp = spacy.load("en_core_web_sm")
    summary = {
        "protocol": "ALOHa official local variant: SpacyObjectParser + MPNetSimilarity + Hungarian/min",
        "adaptation": "Text references/facts only; no MGA parser, masks, temporal direction, or location logic.",
        "spacy_model": "en_core_web_sm 3.7.1 (official local parser interface; paper repository defaults to lg)",
        "mpnet_model": "/root/mga-external/models/all-mpnet-base-v2",
        "real_outputs": eval_real(evaluator, args.real_manifest, args.output_dir),
        "controlled_errors": eval_controlled(evaluator, args.controlled_manifest, args.output_dir),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
