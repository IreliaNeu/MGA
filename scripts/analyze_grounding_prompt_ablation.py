"""Isolate terminal-period prompt formatting from synonym expansion effects."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from mga.grounding.hf_dino_expanded import ExpandedHFGroundingDinoGrounder
from mga.grounding.query_expansion import format_grounding_query
from mga.io import load_manifest
from mga.mask_ops import load_label_mask, select_change_mask
from mga.models import ClaimRole, SampleRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--synonym-details", required=True, type=Path)
    parser.add_argument("--details-output", required=True, type=Path)
    parser.add_argument("--report-output", required=True, type=Path)
    parser.add_argument("--model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--box-threshold", type=float, default=0.30)
    parser.add_argument("--text-threshold", type=float, default=0.25)
    return parser


def _task_key(record: SampleRecord, entity: str) -> tuple[str, str]:
    return (record.sample_id, entity)


def _precision(support: np.ndarray, target: np.ndarray) -> float | None:
    denominator = int(support.sum())
    if denominator == 0:
        return None
    return float(np.logical_and(support, target).sum() / denominator)


def _mean(rows: list[dict[str, Any]], variant: str, field: str) -> float:
    values = [row[variant][field] for row in rows if row[variant][field] is not None]
    return float(statistics.mean(values)) if values else 0.0


def main() -> int:
    args = build_parser().parse_args()
    records = load_manifest(args.manifest)
    tasks: dict[tuple[str, str], tuple[SampleRecord, str]] = {}
    for record in records:
        for claim in record.claims:
            if claim.role == ClaimRole.NO_CHANGE or claim.entity == "scene":
                continue
            tasks.setdefault(_task_key(record, claim.entity), (record, claim.entity))

    synonym_rows = {
        (row["sample_id"], row["entity"]): row
        for row in (
            json.loads(line)
            for line in args.synonym_details.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    grounder = ExpandedHFGroundingDinoGrounder(
        model_id=args.model,
        device=args.device,
        box_threshold=args.box_threshold,
        text_threshold=args.text_threshold,
    )
    output_rows: list[dict[str, Any]] = []
    for key, (record, entity) in tasks.items():
        source = synonym_rows[key]
        prompt = format_grounding_query((entity,))
        pre_mask, pre_confidence, pre_boxes = grounder._ground_image(record.pre_image, prompt)
        post_mask, post_confidence, post_boxes = grounder._ground_image(
            record.post_image, prompt
        )
        support = np.logical_or(pre_mask, post_mask)
        label_mask = load_label_mask(record.change_mask)
        labels = tuple(int(value) for value in record.metadata.get("mask_labels", ()))
        change_mask = select_change_mask(label_mask, labels)
        output_rows.append(
            {
                "sample_id": record.sample_id,
                "entity": entity,
                "raw": source["baseline"],
                "punctuated": {
                    "prompt": prompt,
                    "pre_boxes": pre_boxes,
                    "post_boxes": post_boxes,
                    "total_boxes": pre_boxes + post_boxes,
                    "confidence": max(pre_confidence, post_confidence),
                    "support_pixels": int(support.sum()),
                    "change_overlap_precision": _precision(support, change_mask),
                },
                "synonyms": source["expanded"],
                "expanded_queries": source["expanded_queries"],
            }
        )

    pixels_per_image = 256 * 256
    report = {
        "tasks": len(output_rows),
        "raw_detected": sum(row["raw"]["total_boxes"] > 0 for row in output_rows),
        "punctuated_detected": sum(
            row["punctuated"]["total_boxes"] > 0 for row in output_rows
        ),
        "synonyms_detected": sum(
            row["synonyms"]["total_boxes"] > 0 for row in output_rows
        ),
        "raw_mean_confidence": _mean(output_rows, "raw", "confidence"),
        "punctuated_mean_confidence": _mean(output_rows, "punctuated", "confidence"),
        "synonyms_mean_confidence": _mean(output_rows, "synonyms", "confidence"),
        "punctuated_mean_change_overlap_precision": _mean(
            output_rows, "punctuated", "change_overlap_precision"
        ),
        "synonyms_mean_change_overlap_precision": _mean(
            output_rows, "synonyms", "change_overlap_precision"
        ),
        "punctuated_full_image_supports": sum(
            row["punctuated"]["support_pixels"] == pixels_per_image for row in output_rows
        ),
        "synonyms_full_image_supports": sum(
            row["synonyms"]["support_pixels"] == pixels_per_image for row in output_rows
        ),
    }
    args.details_output.parent.mkdir(parents=True, exist_ok=True)
    with args.details_output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
