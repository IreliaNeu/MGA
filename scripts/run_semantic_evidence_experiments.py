"""Run four evidence routes on controlled semantic-change language samples."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from mga.evidence_routing import (
    grounder_diagnostics,
    score_evidence_modes,
    summarize_scores,
)
from mga.grounding.segearth_ov3 import SegEarthOV3Grounder
from mga.semantic_change import load_label_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument(
        "--class-map",
        required=True,
        help='JSON id-to-name map, e.g. \'{"1":"tree","2":"building"}\'',
    )
    parser.add_argument(
        "--hidden-entities",
        default="",
        help="Comma-separated entities hidden from GTClassLookup/Hybrid.",
    )
    parser.add_argument("--max-scenes", type=int, default=0)
    parser.add_argument(
        "--vendor-root",
        default="/root/autodl-tmp/third_party/SegEarth-OV-3",
    )
    parser.add_argument("--checkpoint")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--logit-threshold", type=float, default=0.10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    class_names = {int(key): str(value) for key, value in json.loads(args.class_map).items()}
    class_ids = {value: key for key, value in class_names.items()}
    hidden_entities = {
        item.strip() for item in args.hidden_entities.split(",") if item.strip()
    }
    all_entities = set(class_ids)
    visible_hidden_condition = all_entities - hidden_entities
    items = [
        json.loads(line)
        for line in args.samples.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[str(item["sample_id"])].append(item)
    if args.max_scenes > 0:
        allowed = set(sorted(grouped)[: args.max_scenes])
        grouped = {key: grouped[key] for key in sorted(allowed)}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    grounder = SegEarthOV3Grounder(
        vendor_root=args.vendor_root,
        checkpoint_path=args.checkpoint,
        device=args.device,
        confidence_threshold=args.confidence_threshold,
        logit_threshold=args.logit_threshold,
    )
    rows_by_condition: dict[str, list[dict]] = {
        "closed_set": [],
        "hidden_class": [],
    }
    diagnostic_rows = []
    start_time = time.perf_counter()
    for scene_index, (sample_id, scene_items) in enumerate(sorted(grouped.items()), start=1):
        representative = scene_items[0]
        requested_entities = tuple(
            sorted(
                {
                    str(claim["entity"])
                    for item in scene_items
                    for claim in item["claims"]
                }
            )
        )
        open_vocab = load_or_ground(
            grounder=grounder,
            sample_id=sample_id,
            pre_image=representative["pre_image"],
            post_image=representative["post_image"],
            entities=requested_entities,
            cache_dir=args.cache_dir,
        )
        semantic_pre = load_label_ids(representative["pre_label"])
        semantic_post = load_label_ids(representative["post_label"])
        diagnostic_rows.extend(
            {
                "sample_id": sample_id,
                **row,
            }
            for row in grounder_diagnostics(
                semantic_pre=semantic_pre,
                semantic_post=semantic_post,
                class_ids=class_ids,
                open_vocab=open_vocab,
            )
        )
        for condition, visible_entities in (
            ("closed_set", all_entities),
            ("hidden_class", visible_hidden_condition),
        ):
            for item in scene_items:
                scores = score_evidence_modes(
                    claims=item["claims"],
                    semantic_pre=semantic_pre,
                    semantic_post=semantic_post,
                    class_ids=class_ids,
                    visible_entities=visible_entities,
                    open_vocab=open_vocab,
                )
                rows_by_condition[condition].append(
                    {
                        "sample_id": sample_id,
                        "item_id": item["item_id"],
                        "sample_type": item["sample_type"],
                        "caption": item["caption"],
                        "is_factually_correct": item["is_factually_correct"],
                        "visible_entities": sorted(visible_entities),
                        "scores": scores,
                    }
                )
        if scene_index % 10 == 0 or scene_index == len(grouped):
            elapsed = time.perf_counter() - start_time
            print(
                f"processed {scene_index}/{len(grouped)} scenes in {elapsed:.1f}s",
                flush=True,
            )

    for condition, rows in rows_by_condition.items():
        write_jsonl(args.output_dir / f"{condition}_scores.jsonl", rows)
    write_jsonl(args.output_dir / "grounder_diagnostics.jsonl", diagnostic_rows)
    summary = {
        "scene_count": len(grouped),
        "item_count": sum(len(value) for value in grouped.values()),
        "class_map": class_names,
        "hidden_entities": sorted(hidden_entities),
        "runtime_seconds": time.perf_counter() - start_time,
        "grounder_backend": grounder.backend_id,
        "conditions": {
            condition: summarize_scores(rows)
            for condition, rows in rows_by_condition.items()
        },
        "grounder": summarize_grounder(diagnostic_rows),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


def load_or_ground(
    *,
    grounder: SegEarthOV3Grounder,
    sample_id: str,
    pre_image: str,
    post_image: str,
    entities: tuple[str, ...],
    cache_dir: Path,
) -> dict[str, dict]:
    cache_path = cache_dir / f"{sample_id}.npz"
    if cache_path.is_file():
        with np.load(cache_path, allow_pickle=False) as value:
            cached_entities = json.loads(str(value["entities_json"].item()))
            if tuple(cached_entities) == entities:
                return {
                    entity: {
                        "pre_mask": value["pre_masks"][index].astype(bool),
                        "post_mask": value["post_masks"][index].astype(bool),
                        "pre_confidence": float(value["pre_confidences"][index]),
                        "post_confidence": float(value["post_confidences"][index]),
                    }
                    for index, entity in enumerate(cached_entities)
                }
    pre_results = grounder.segment_queries(pre_image, entities)
    post_results = grounder.segment_queries(post_image, entities)
    result = {
        entity: {
            "pre_mask": pre_results[entity].mask,
            "post_mask": post_results[entity].mask,
            "pre_confidence": pre_results[entity].confidence,
            "post_confidence": post_results[entity].confidence,
        }
        for entity in entities
    }
    np.savez_compressed(
        cache_path,
        entities_json=np.asarray(json.dumps(list(entities))),
        pre_masks=np.stack([result[entity]["pre_mask"] for entity in entities]),
        post_masks=np.stack([result[entity]["post_mask"] for entity in entities]),
        pre_confidences=np.asarray(
            [result[entity]["pre_confidence"] for entity in entities]
        ),
        post_confidences=np.asarray(
            [result[entity]["post_confidence"] for entity in entities]
        ),
    )
    return result


def summarize_grounder(rows: list[dict]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["entity"])].append(row)
    summary = {}
    for entity, values in sorted(grouped.items()):
        item = {"n": len(values)}
        for key in (
            "pre_iou",
            "post_iou",
            "add_iou",
            "remove_iou",
            "pre_confidence",
            "post_confidence",
            "pre_fraction",
            "post_fraction",
        ):
            scores = [
                float(value[key])
                for value in values
                if value.get(key) is not None
            ]
            item[f"mean_{key}"] = (
                sum(scores) / len(scores) if scores else float("nan")
            )
        summary[entity] = item
    return summary


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")


if __name__ == "__main__":
    main()
