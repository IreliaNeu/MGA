"""Measure Hybrid evidence quality across exhaustive semantic-label subsets."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from mga.evidence_routing import balanced_accuracy, binary_auc
from mga.evidence_routing_v2 import relation_score
from mga.semantic_change import load_label_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--class-map", required=True)
    parser.add_argument("--min-ov-confidence", type=float, default=0.10)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_open_vocab(path: Path) -> dict[str, dict]:
    with np.load(path, allow_pickle=False) as values:
        entities = json.loads(str(values["entities_json"].item()))
        return {
            entity: {
                "pre_mask": values["pre_masks"][index].astype(bool),
                "post_mask": values["post_masks"][index].astype(bool),
                "pre_confidence": float(values["pre_confidences"][index]),
                "post_confidence": float(values["post_confidences"][index]),
            }
            for index, entity in enumerate(entities)
        }


def claim_pair(item: dict) -> tuple[dict, dict]:
    source = next(
        (claim for claim in item["claims"] if claim["change_type"] == "remove"),
        item["claims"][0],
    )
    target = next(
        (claim for claim in item["claims"] if claim["change_type"] == "add"),
        item["claims"][-1],
    )
    return source, target


def masks_for(
    entity: str,
    backend: str,
    *,
    semantic_pre: np.ndarray,
    semantic_post: np.ndarray,
    class_ids: dict[str, int],
    open_vocab: dict[str, dict],
    role: str,
    min_ov_confidence: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    if backend == "gt":
        if entity not in class_ids:
            return None
        class_id = class_ids[entity]
        return semantic_pre == class_id, semantic_post == class_id
    values = open_vocab.get(entity)
    if values is None:
        return None
    required_mask = values["pre_mask"] if role == "source" else values["post_mask"]
    required_confidence = (
        values["pre_confidence"] if role == "source" else values["post_confidence"]
    )
    if required_confidence < min_ov_confidence or not required_mask.any():
        return None
    return values["pre_mask"], values["post_mask"]


def precompute_route_states(
    *,
    items: list[dict],
    cache_dir: Path,
    class_ids: dict[str, int],
    min_ov_confidence: float,
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[str(item["sample_id"])].append(item)
    rows = []
    for index, (sample_id, scene_items) in enumerate(sorted(grouped.items()), start=1):
        representative = scene_items[0]
        semantic_pre = load_label_ids(representative["pre_label"])
        semantic_post = load_label_ids(representative["post_label"])
        cache_path = cache_dir / f"{sample_id}.npz"
        if not cache_path.is_file():
            raise FileNotFoundError(f"Missing SegEarth cache: {cache_path}")
        open_vocab = load_open_vocab(cache_path)
        for item in scene_items:
            source_claim, target_claim = claim_pair(item)
            source = str(source_claim["entity"])
            target = str(target_claim["entity"])
            location = str(
                source_claim.get("location")
                or target_claim.get("location")
                or ""
            )
            states = {}
            for source_backend, target_backend in itertools.product(
                ("ov", "gt"), repeat=2
            ):
                states[f"{source_backend}_{target_backend}"] = relation_score(
                    source_masks=masks_for(
                        source,
                        source_backend,
                        semantic_pre=semantic_pre,
                        semantic_post=semantic_post,
                        class_ids=class_ids,
                        open_vocab=open_vocab,
                        role="source",
                        min_ov_confidence=min_ov_confidence,
                    ),
                    target_masks=masks_for(
                        target,
                        target_backend,
                        semantic_pre=semantic_pre,
                        semantic_post=semantic_post,
                        class_ids=class_ids,
                        open_vocab=open_vocab,
                        role="target",
                        min_ov_confidence=min_ov_confidence,
                    ),
                    location=location,
                    semantic_pre=semantic_pre,
                    semantic_post=semantic_post,
                )
            rows.append(
                {
                    "sample_id": sample_id,
                    "item_id": item["item_id"],
                    "is_factually_correct": bool(item["is_factually_correct"]),
                    "source": source,
                    "target": target,
                    "states": states,
                }
            )
        if index % 25 == 0 or index == len(grouped):
            print(f"precomputed {index}/{len(grouped)} scenes", flush=True)
    return rows


def score_for_subset(row: dict, visible: set[str]) -> float | None:
    source_backend = "gt" if row["source"] in visible else "ov"
    target_backend = "gt" if row["target"] in visible else "ov"
    return row["states"][f"{source_backend}_{target_backend}"]


def metrics(values: list[tuple[bool, float | None]]) -> dict[str, float | int]:
    available = [
        (label, float(score)) for label, score in values if score is not None
    ]
    neutral = [
        (label, 0.5 if score is None else float(score))
        for label, score in values
    ]
    negatives = [score for label, score in available if not label]
    coverage = len(available) / max(len(values), 1)
    return {
        "n": len(values),
        "n_scored": len(available),
        "coverage": coverage,
        "neutral_auc": binary_auc(neutral),
        "balanced_accuracy": balanced_accuracy(available),
        "false_support_rate": (
            sum(score >= 0.5 for score in negatives) / len(negatives)
            if negatives
            else float("nan")
        ),
        "unverifiable_rate": 1.0 - coverage,
    }


def aggregate(points: list[dict], class_count: int) -> dict:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for point in points:
        grouped[int(point["visible_class_count"])].append(point)
    curve = []
    metric_names = (
        "coverage",
        "neutral_auc",
        "balanced_accuracy",
        "false_support_rate",
        "unverifiable_rate",
    )
    for visible_count in range(class_count + 1):
        values = grouped[visible_count]
        item = {
            "visible_class_count": visible_count,
            "availability": visible_count / class_count,
            "subset_count": len(values),
        }
        for metric_name in metric_names:
            scores = [
                float(point["metrics"][metric_name])
                for point in values
                if not math.isnan(float(point["metrics"][metric_name]))
            ]
            item[metric_name] = sum(scores) / len(scores) if scores else float("nan")
            item[f"{metric_name}_min"] = min(scores) if scores else float("nan")
            item[f"{metric_name}_max"] = max(scores) if scores else float("nan")
        curve.append(item)
    return {"curve": curve}


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    class_map_value = args.class_map
    class_map_path = Path(class_map_value)
    if class_map_path.is_file():
        class_map_value = class_map_path.read_text(encoding="utf-8")
    class_names = {
        int(key): str(value)
        for key, value in json.loads(class_map_value).items()
    }
    class_ids = {value: key for key, value in class_names.items()}
    started = time.perf_counter()
    state_rows = precompute_route_states(
        items=read_jsonl(args.samples),
        cache_dir=args.cache_dir,
        class_ids=class_ids,
        min_ov_confidence=args.min_ov_confidence,
    )
    classes = tuple(sorted(class_ids))
    points = []
    for visible_count in range(len(classes) + 1):
        for subset in itertools.combinations(classes, visible_count):
            visible = set(subset)
            values = [
                (row["is_factually_correct"], score_for_subset(row, visible))
                for row in state_rows
            ]
            points.append(
                {
                    "visible_classes": list(subset),
                    "visible_class_count": visible_count,
                    "availability": visible_count / len(classes),
                    "metrics": metrics(values),
                }
            )
    summary = {
        "method": "MGA-Hybrid",
        "scene_count": len({row["sample_id"] for row in state_rows}),
        "item_count": len(state_rows),
        "classes": list(classes),
        "class_count": len(classes),
        "subset_count": len(points),
        "subset_protocol": "exhaustive_power_set",
        "verifiability_protocol": {
            "min_ov_confidence": args.min_ov_confidence,
            "required_source_evidence": "non-empty T1 mask",
            "required_target_evidence": "non-empty T2 mask",
        },
        "metric_definition": {
            "coverage": "fraction of items receiving a numeric Hybrid score",
            "neutral_auc": "ROC-AUC with unverifiable items assigned score 0.5",
            "balanced_accuracy": "balanced accuracy at threshold 0.5 on scored items",
            "false_support_rate": "fraction of contradicted items scored at least 0.5",
            "unverifiable_rate": "one minus score coverage",
        },
        **aggregate(points, len(classes)),
        "runtime_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "curve_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    with (args.output_dir / "per_subset.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for point in points:
            handle.write(json.dumps(point, ensure_ascii=False, allow_nan=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
