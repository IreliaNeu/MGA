"""Compare original and synonym-expanded Grounding DINO queries on a manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from mga.grounding.hf_dino_expanded import ExpandedHFGroundingDinoGrounder
from mga.grounding.query_expansion import expand_grounding_queries, format_grounding_query
from mga.io import load_manifest
from mga.mask_ops import load_label_mask, select_change_mask
from mga.models import ClaimRole, SampleRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--details-output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    parser.add_argument("--model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--box-threshold", type=float, default=0.30)
    parser.add_argument("--text-threshold", type=float, default=0.25)
    parser.add_argument("--profile", default="remote-sensing")
    return parser


def _union(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.logical_or(np.asarray(left, dtype=bool), np.asarray(right, dtype=bool))


def _overlap_precision(support: np.ndarray, target: np.ndarray) -> float | None:
    denominator = int(support.sum())
    if denominator == 0:
        return None
    return float(np.logical_and(support, target).sum() / denominator)


def _task_key(record: SampleRecord, entity: str) -> tuple[str, str, str, str, str]:
    return (record.sample_id, entity, record.pre_image, record.post_image, record.change_mask)


def analyze(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = load_manifest(args.manifest)
    tasks: dict[tuple[str, str, str, str, str], tuple[SampleRecord, str]] = {}
    for record in records:
        for claim in record.claims:
            if claim.role == ClaimRole.NO_CHANGE or claim.entity == "scene":
                continue
            tasks.setdefault(_task_key(record, claim.entity), (record, claim.entity))

    grounder = ExpandedHFGroundingDinoGrounder(
        model_id=args.model,
        device=args.device,
        box_threshold=args.box_threshold,
        text_threshold=args.text_threshold,
        query_expansion=args.profile,
    )
    details: list[dict[str, Any]] = []
    for record, entity in tasks.values():
        baseline_prompt = entity
        expanded_queries = expand_grounding_queries(entity, args.profile)
        expanded_prompt = format_grounding_query(expanded_queries)

        baseline_pre = grounder._ground_image(record.pre_image, baseline_prompt)
        baseline_post = grounder._ground_image(record.post_image, baseline_prompt)
        expanded_pre = grounder._ground_image(record.pre_image, expanded_prompt)
        expanded_post = grounder._ground_image(record.post_image, expanded_prompt)

        label_mask = load_label_mask(record.change_mask)
        labels = tuple(int(value) for value in record.metadata.get("mask_labels", ()))
        change_mask = select_change_mask(label_mask, labels)
        baseline_support = _union(baseline_pre[0], baseline_post[0])
        expanded_support = _union(expanded_pre[0], expanded_post[0])
        baseline_boxes = baseline_pre[2] + baseline_post[2]
        expanded_boxes = expanded_pre[2] + expanded_post[2]
        baseline_confidence = max(baseline_pre[1], baseline_post[1])
        expanded_confidence = max(expanded_pre[1], expanded_post[1])

        details.append(
            {
                "sample_id": record.sample_id,
                "entity": entity,
                "baseline_prompt": baseline_prompt,
                "expanded_queries": list(expanded_queries),
                "expanded_prompt": expanded_prompt,
                "baseline": {
                    "pre_boxes": baseline_pre[2],
                    "post_boxes": baseline_post[2],
                    "total_boxes": baseline_boxes,
                    "confidence": baseline_confidence,
                    "support_pixels": int(baseline_support.sum()),
                    "change_overlap_precision": _overlap_precision(
                        baseline_support, change_mask
                    ),
                },
                "expanded": {
                    "pre_boxes": expanded_pre[2],
                    "post_boxes": expanded_post[2],
                    "total_boxes": expanded_boxes,
                    "confidence": expanded_confidence,
                    "support_pixels": int(expanded_support.sum()),
                    "change_overlap_precision": _overlap_precision(
                        expanded_support, change_mask
                    ),
                },
                "rescued_detection": baseline_boxes == 0 and expanded_boxes > 0,
                "lost_detection": baseline_boxes > 0 and expanded_boxes == 0,
            }
        )

    entity_stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in details:
        entity = str(row["entity"])
        entity_stats[entity]["tasks"] += 1
        entity_stats[entity]["baseline_detected"] += int(row["baseline"]["total_boxes"] > 0)
        entity_stats[entity]["expanded_detected"] += int(row["expanded"]["total_boxes"] > 0)
        entity_stats[entity]["rescued"] += int(row["rescued_detection"])
        entity_stats[entity]["lost"] += int(row["lost_detection"])

    report = {
        "manifest": str(args.manifest),
        "model": args.model,
        "profile": args.profile,
        "box_threshold": args.box_threshold,
        "text_threshold": args.text_threshold,
        "tasks": len(details),
        "baseline_detected_tasks": sum(row["baseline"]["total_boxes"] > 0 for row in details),
        "expanded_detected_tasks": sum(row["expanded"]["total_boxes"] > 0 for row in details),
        "rescued_detections": sum(row["rescued_detection"] for row in details),
        "lost_detections": sum(row["lost_detection"] for row in details),
        "mean_baseline_confidence": float(
            np.mean([row["baseline"]["confidence"] for row in details]) if details else 0.0
        ),
        "mean_expanded_confidence": float(
            np.mean([row["expanded"]["confidence"] for row in details]) if details else 0.0
        ),
        "by_entity": {entity: dict(counts) for entity, counts in sorted(entity_stats.items())},
    }
    return details, report


def main() -> int:
    args = build_parser().parse_args()
    details, report = analyze(args)
    args.details_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    with args.details_output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in details:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
