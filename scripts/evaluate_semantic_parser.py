"""Compare ontology-only and lightweight-model-assisted entity extraction."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from mga.parsing.hybrid import GlinerEntityExtractor, HybridEntityClaimParser
from mga.parsing.ontology import EntityOntology, REMOTE_SENSING_ALIASES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--class-map",
        required=True,
        help='JSON id-to-name map, e.g. \'{"1":"tree","2":"building"}\'',
    )
    parser.add_argument("--model-name", default="urchade/gliner_small-v2.1")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--skip-model", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    class_names = {int(key): str(value) for key, value in json.loads(args.class_map).items()}
    aliases = {}
    label_map = {}
    for class_id, entity in class_names.items():
        aliases[entity] = REMOTE_SENSING_ALIASES.get(
            entity,
            (entity, f"{entity}s"),
        )
        label_map[entity] = (class_id,)
    ontology = EntityOntology(
        aliases=aliases,
        label_map=label_map,
        allow_unknown=True,
    )
    items = [
        json.loads(line)
        for line in args.samples.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    parsers = {"ontology_only": HybridEntityClaimParser(ontology=ontology)}
    if not args.skip_model:
        parsers["ontology_gliner"] = HybridEntityClaimParser(
            ontology=ontology,
            extractor=GlinerEntityExtractor(
                model_name=args.model_name,
                threshold=args.threshold,
                device=args.device,
            ),
        )

    report = {
        "item_count": len(items),
        "class_map": class_names,
        "model_name": None if args.skip_model else args.model_name,
        "parsers": {},
    }
    for name, parser in parsers.items():
        start = time.perf_counter()
        rows = []
        for item in items:
            expected = {
                (str(claim["entity"]), str(claim["change_type"]))
                for claim in item["claims"]
            }
            predicted_claims = parser.parse(item["caption"])
            predicted = {
                (claim.entity, claim.change_type.value) for claim in predicted_claims
            }
            rows.append(
                {
                    "item_id": item["item_id"],
                    "sample_type": item["sample_type"],
                    "expected": sorted(expected),
                    "predicted": sorted(predicted),
                    "true_positive": len(expected & predicted),
                    "false_positive": len(predicted - expected),
                    "false_negative": len(expected - predicted),
                    "exact": expected == predicted,
                }
            )
        report["parsers"][name] = summarize(rows)
        report["parsers"][name]["runtime_seconds"] = time.perf_counter() - start
        report["parsers"][name]["rows"] = rows
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compact = {
        **{key: value for key, value in report.items() if key != "parsers"},
        "parsers": {
            key: {metric: value for metric, value in result.items() if metric != "rows"}
            for key, result in report["parsers"].items()
        },
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


def summarize(rows: list[dict]) -> dict:
    true_positive = sum(row["true_positive"] for row in rows)
    false_positive = sum(row["false_positive"] for row in rows)
    false_negative = sum(row["false_negative"] for row in rows)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    by_type: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_type[row["sample_type"]].append(bool(row["exact"]))
    return {
        "exact_match": sum(row["exact"] for row in rows) / max(len(rows), 1),
        "claim_precision": precision,
        "claim_recall": recall,
        "claim_f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "by_sample_type_exact": {
            key: sum(values) / len(values) for key, values in sorted(by_type.items())
        },
    }


if __name__ == "__main__":
    main()
