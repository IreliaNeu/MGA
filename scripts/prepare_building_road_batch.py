"""Audit LEVIR-MCI alignment and build a building/road-only MGA manifest."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from mga.io import load_manifest, write_jsonl
from mga.mask_ops import load_label_mask
from mga.models import ClaimRole, SampleRecord
from mga.parsing import HeuristicClaimParser

TARGET_LABELS = (1, 2)
EXPECTED_CLASS_MAP = {"0": "background", "1": "road", "2": "building"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--audit-report", required=True, type=Path)
    parser.add_argument("--max-scenes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument(
        "--sample-id-file",
        type=Path,
        help="Optional newline-delimited scene IDs; preserves this order and disables sampling.",
    )
    parser.add_argument(
        "--allow-empty-target-mask",
        action="store_true",
        help="Keep named validation scenes without road/building change pixels.",
    )
    parser.add_argument(
        "--allow-no-target-change-claims",
        action="store_true",
        help="Keep scenes whose three captions contain no parsed road/building change claim.",
    )
    parser.add_argument(
        "--require-models",
        nargs="+",
        default=("Draft", "Guided", "Change-Agent"),
    )
    return parser


def _image_size(path: str) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _audit_scene(
    records: list[SampleRecord], required_models: tuple[str, ...]
) -> tuple[list[str], np.ndarray | None]:
    issues = []
    models = tuple(sorted(record.model for record in records))
    if models != tuple(sorted(required_models)):
        issues.append("model_set_mismatch")

    path_sets = {
        field: {getattr(record, field) for record in records}
        for field in ("pre_image", "post_image", "change_mask")
    }
    if any(len(paths) != 1 for paths in path_sets.values()):
        issues.append("cross_model_path_mismatch")
        return issues, None

    paths = {
        field: next(iter(values)) for field, values in path_sets.items()
    }
    if any(not Path(path).is_file() for path in paths.values()):
        issues.append("missing_file")
        return issues, None

    stems = {Path(path).stem for path in paths.values()}
    if len(stems) != 1:
        issues.append("image_mask_stem_mismatch")

    source_stems = {
        str(record.metadata.get("source_image_stem", "")) for record in records
    }
    if source_stems != stems:
        issues.append("metadata_stem_mismatch")

    try:
        pre_size = _image_size(paths["pre_image"])
        post_size = _image_size(paths["post_image"])
        mask = load_label_mask(paths["change_mask"])
    except (OSError, ValueError):
        issues.append("unreadable_image_or_mask")
        return issues, None
    if pre_size != post_size or pre_size != (mask.shape[1], mask.shape[0]):
        issues.append("shape_mismatch")

    values = set(int(value) for value in np.unique(mask))
    if not values.issubset({0, *TARGET_LABELS}):
        issues.append("unexpected_mask_label")
    if not values.intersection(TARGET_LABELS):
        issues.append("no_building_or_road_change")

    class_maps = {
        json.dumps(record.metadata.get("mask_class_map", {}), sort_keys=True)
        for record in records
    }
    if class_maps != {json.dumps(EXPECTED_CLASS_MAP, sort_keys=True)}:
        issues.append("mask_class_map_mismatch")
    return issues, mask


def _enrich(records: list[SampleRecord]) -> list[SampleRecord]:
    parser = HeuristicClaimParser()
    enriched = []
    for record in records:
        metadata = {
            **record.metadata,
            "mask_labels": list(TARGET_LABELS),
            "evaluation_entities": ["building", "road"],
            "claim_parser": "heuristic-building-road-v4",
        }
        enriched.append(
            replace(record, claims=parser.parse(record.caption), metadata=metadata)
        )
    return enriched


def main() -> int:
    args = build_parser().parse_args()
    if args.max_scenes < 1:
        raise ValueError("--max-scenes must be positive")
    records = load_manifest(args.manifest)
    grouped: dict[str, list[SampleRecord]] = defaultdict(list)
    for record in records:
        grouped[record.sample_id].append(record)
    requested_ids: list[str] = []
    missing_requested_ids: list[str] = []
    if args.sample_id_file is not None:
        requested_ids = [
            value.strip().lower()
            for value in args.sample_id_file.read_text(encoding="utf-8").splitlines()
            if value.strip()
        ]
        if len(requested_ids) != len(set(requested_ids)):
            raise ValueError("--sample-id-file contains duplicate scene IDs")
        grouped_by_lower = {sample_id.lower(): rows for sample_id, rows in grouped.items()}
        missing_requested_ids = [
            sample_id for sample_id in requested_ids if sample_id not in grouped_by_lower
        ]
        grouped = {
            sample_id: grouped_by_lower[sample_id]
            for sample_id in requested_ids
            if sample_id in grouped_by_lower
        }

    eligible: list[tuple[str, list[SampleRecord]]] = []
    excluded: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    mask_scene_counts: Counter[str] = Counter()
    parser_counts: Counter[str] = Counter()
    required_models = tuple(args.require_models)
    for sample_id, scene_records in sorted(grouped.items()):
        issues, mask = _audit_scene(scene_records, required_models)
        enriched = _enrich(scene_records)
        changed_claims = [
            claim
            for record in enriched
            for claim in record.claims
            if claim.role == ClaimRole.CHANGED
        ]
        if not changed_claims:
            issues.append("no_target_change_claim_in_any_caption")
        for claim in changed_claims:
            parser_counts[f"{claim.entity}:{claim.change_type.value}"] += 1
        if mask is not None:
            values = set(int(value) for value in np.unique(mask))
            for label, name in ((1, "road"), (2, "building")):
                if label in values:
                    mask_scene_counts[name] += 1
        if args.allow_empty_target_mask:
            issues = [issue for issue in issues if issue != "no_building_or_road_change"]
        if args.allow_no_target_change_claims:
            issues = [
                issue
                for issue in issues
                if issue != "no_target_change_claim_in_any_caption"
            ]
        if issues:
            unique_issues = sorted(set(issues))
            issue_counts.update(unique_issues)
            excluded.append({"sample_id": sample_id, "issues": unique_issues})
            continue
        eligible.append((sample_id, enriched))

    if requested_ids:
        eligible_by_lower = {sample_id.lower(): rows for sample_id, rows in eligible}
        selected = [
            (sample_id, eligible_by_lower[sample_id])
            for sample_id in requested_ids
            if sample_id in eligible_by_lower
        ]
    else:
        rng = random.Random(args.seed)
        rng.shuffle(eligible)
        selected = eligible[: args.max_scenes]
        selected.sort(key=lambda item: item[0])
    output_records = [record for _sample_id, rows in selected for record in rows]
    if not output_records:
        raise ValueError("No eligible scenes remain after alignment and claim auditing")
    write_jsonl(args.output_manifest, (record.to_dict() for record in output_records))

    report = {
        "source_manifest": str(args.manifest.resolve()),
        "output_manifest": str(args.output_manifest.resolve()),
        "seed": args.seed,
        "selection_method": "named_scenes" if requested_ids else "seeded_sample",
        "sample_id_file": (
            str(args.sample_id_file.resolve()) if args.sample_id_file is not None else None
        ),
        "requested_sample_ids": requested_ids,
        "missing_requested_ids": missing_requested_ids,
        "required_models": list(required_models),
        "target_entities": {"road": 1, "building": 2},
        "counts": {
            "input_records": len(records),
            "input_scenes": len(grouped),
            "eligible_scenes": len(eligible),
            "selected_scenes": len(selected),
            "selected_records": len(output_records),
            "excluded_scenes": len(excluded),
        },
        "mask_scene_counts_before_selection": dict(mask_scene_counts),
        "parser_changed_claim_counts_before_selection": dict(parser_counts),
        "issue_counts": dict(issue_counts),
        "excluded": excluded,
        "selected_sample_ids": [sample_id for sample_id, _records in selected],
    }
    args.audit_report.parent.mkdir(parents=True, exist_ok=True)
    args.audit_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
