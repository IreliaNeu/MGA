"""Build and audit a five-model LEVIR-MCI caption manifest for P0-1."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from mga.io import read_jsonl, write_jsonl
from mga.parsing import HeuristicClaimParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", required=True, type=Path)
    parser.add_argument("--rsiccformer", required=True, type=Path)
    parser.add_argument("--chg2cap", required=True, type=Path)
    parser.add_argument("--caption-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scene-id-file", type=Path)
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_id(value: str) -> str:
    original = value.strip().lower()
    if original.startswith('levir-cc_test_'):
        return original
    if original.startswith('test_'):
        return f'levir-cc_{original}'
    value = value.strip().lower().replace("_", "-")
    if value.startswith("levir-cc-"):
        return value
    if value.startswith("test-"):
        return f"levir-cc-{value}"
    raise ValueError(f"Unsupported LEVIR sample id: {value}")


def reference_index(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    output = {}
    for item in data["images"]:
        if item.get("split") != "test":
            continue
        sample_id = canonical_id(Path(item["filename"]).stem)
        output[sample_id] = [
            str(sentence["raw"]).strip() for sentence in item["sentences"]
        ]
    return output


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    references = reference_index(args.caption_json)
    base_rows = list(read_jsonl(args.base_manifest))
    templates: dict[str, dict] = {}
    rows = []
    source_name = {"Draft": "Draft", "Guided": "Refined", "Change-Agent": "Change-Agent"}
    for raw in base_rows:
        sample_id = canonical_id(str(raw["sample_id"]))
        templates.setdefault(sample_id, raw)
        if raw["model"] not in source_name:
            continue
        rows.append(
            {
                **raw,
                "sample_id": sample_id,
                "model": source_name[raw["model"]],
                "model_family": "Change-Agent" if raw["model"] != "Draft" else "Draft",
                "model_variant": str(raw["model"]),
                "references": references[sample_id],
                "provenance": {
                    "source": str(args.base_manifest.resolve()),
                    "source_sha256": sha256(args.base_manifest),
                    "original_model_field": raw["model"],
                },
            }
        )

    for family, path in (("RSICCformer", args.rsiccformer), ("Chg2Cap", args.chg2cap)):
        for generated in read_jsonl(path):
            sample_id = canonical_id(str(generated["sample_id"]))
            template = templates[sample_id]
            rows.append(
                {
                    "sample_id": sample_id,
                    "dataset": template["dataset"],
                    "split": template.get("split", "test"),
                    "model": family,
                    "model_family": family,
                    "model_variant": generated["model_variant"],
                    "caption": generated["caption"],
                    "pre_image": template["pre_image"],
                    "post_image": template["post_image"],
                    "change_mask": template["change_mask"],
                    "metadata": template.get("metadata", {}),
                    "references": references[sample_id],
                    "provenance": {
                        **generated["provenance"],
                        "output_source": str(path.resolve()),
                        "output_sha256": sha256(path),
                    },
                }
            )

    scene_filter = None
    if args.scene_id_file:
        scene_filter = {
            canonical_id(value)
            for value in args.scene_id_file.read_text(encoding="utf-8").splitlines()
            if value.strip()
        }
    claim_parser = HeuristicClaimParser()
    model_counts: Counter[str] = Counter()
    parser_counts: dict[str, Counter[str]] = defaultdict(Counter)
    parser_manifest = []
    for row in sorted(rows, key=lambda item: (item["sample_id"], item["model"])):
        model = str(row["model"])
        model_counts[model] += 1
        claims = claim_parser.parse(str(row["caption"]))
        parser_counts[model]["captions"] += 1
        parser_counts[model]["claims"] += len(claims)
        parser_counts[model]["no_claim"] += int(not claims)
        parser_counts[model]["no_change"] += int(
            any(claim.entity == "scene" for claim in claims)
        )
        parser_counts[model]["building_claim"] += int(
            any(claim.entity == "building" for claim in claims)
        )
        parser_counts[model]["road_claim"] += int(
            any(claim.entity == "road" for claim in claims)
        )
        enriched = {**row, "claims": [claim.to_dict() for claim in claims]}
        if scene_filter is None or row["sample_id"] in scene_filter:
            parser_manifest.append(enriched)

    expected_models = {"Draft", "Refined", "Change-Agent", "RSICCformer", "Chg2Cap"}
    scene_models: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scene_models[row["sample_id"]].add(row["model"])
    invalid_scenes = sorted(
        sample_id for sample_id, models in scene_models.items() if models != expected_models
    )
    if invalid_scenes:
        raise ValueError(f"Model-set mismatch for {len(invalid_scenes)} scenes")
    if len(scene_models) != 1000 or len(rows) != 5000:
        raise ValueError(f"Expected 1000 scenes/5000 rows, got {len(scene_models)}/{len(rows)}")

    manifest_path = args.output_dir / "model_outputs_manifest.jsonl"
    parser_path = args.output_dir / (
        "model_outputs_cached_scenes_claims.jsonl" if scene_filter else "model_outputs_claims.jsonl"
    )
    write_jsonl(manifest_path, rows)
    write_jsonl(parser_path, parser_manifest)
    summary = {
        "scenes": len(scene_models),
        "rows": len(rows),
        "models": dict(sorted(model_counts.items())),
        "references_per_scene": sorted({len(value) for value in references.values()}),
        "reference_scene_count": len(references),
        "parser": {model: dict(counts) for model, counts in sorted(parser_counts.items())},
        "selected_parser_rows": len(parser_manifest),
        "selected_scene_count": len({row["sample_id"] for row in parser_manifest}),
        "files": {
            "manifest": str(manifest_path.resolve()),
            "manifest_sha256": sha256(manifest_path),
            "parser_manifest": str(parser_path.resolve()),
            "parser_manifest_sha256": sha256(parser_path),
        },
    }
    summary_path = args.output_dir / "model_outputs_manifest.summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
