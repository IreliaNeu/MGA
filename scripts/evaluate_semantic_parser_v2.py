"""Evaluate configured ontology and lightweight-model Parser variants."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from mga.parsing.configured import (
    configured_entity_ontology,
    load_surface_forms,
)
from mga.parsing.hybrid import GlinerEntityExtractor, HybridEntityClaimParser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--surface-map-file", type=Path, required=True)
    parser.add_argument("--class-map", required=True)
    parser.add_argument("--model-name", default="urchade/gliner_small-v2.1")
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    class_names = {
        int(key): str(value) for key, value in json.loads(args.class_map).items()
    }
    ontology = configured_entity_ontology(
        class_names=class_names,
        surface_forms=load_surface_forms(args.surface_map_file),
    )
    items = [
        json.loads(line)
        for line in args.samples.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    parsers = {
        "configured_ontology": HybridEntityClaimParser(ontology=ontology),
        "configured_ontology_gliner": HybridEntityClaimParser(
            ontology=ontology,
            extractor=GlinerEntityExtractor(
                model_name=args.model_name,
                threshold=args.threshold,
                device=args.device,
            ),
        ),
    }
    report = {
        "item_count": len(items),
        "class_map": class_names,
        "surface_map_file": str(args.surface_map_file),
        "model_name": args.model_name,
        "parsers": {},
    }
    for name, claim_parser in parsers.items():
        started = time.perf_counter()
        rows = []
        for item in items:
            expected = {
                (str(claim["entity"]), str(claim["change_type"]))
                for claim in item["claims"]
            }
            predicted = {
                (claim.entity, claim.change_type.value)
                for claim in claim_parser.parse(item["caption"])
            }
            rows.append(
                {
                    "item_id": item["item_id"],
                    "sample_type": item["sample_type"],
                    "true_positive": len(expected & predicted),
                    "false_positive": len(predicted - expected),
                    "false_negative": len(expected - predicted),
                    "exact": expected == predicted,
                }
            )
        report["parsers"][name] = summarize(rows)
        report["parsers"][name]["runtime_seconds"] = (
            time.perf_counter() - started
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def summarize(rows: list[dict]) -> dict:
    true_positive = sum(row["true_positive"] for row in rows)
    false_positive = sum(row["false_positive"] for row in rows)
    false_negative = sum(row["false_negative"] for row in rows)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    by_type: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_type[str(row["sample_type"])].append(bool(row["exact"]))
    return {
        "exact_match": sum(row["exact"] for row in rows) / max(len(rows), 1),
        "claim_precision": precision,
        "claim_recall": recall,
        "claim_f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "by_sample_type_exact": {
            key: sum(values) / len(values)
            for key, values in sorted(by_type.items())
        },
    }


if __name__ == "__main__":
    main()
