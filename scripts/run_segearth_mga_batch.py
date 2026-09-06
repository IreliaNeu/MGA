"""Run SegEarth-OV3 once per image, visualize entities, and compute MGA v2 scores."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from mga.grounding.cache import EvidenceCache
from mga.grounding.segearth_ov3 import EntitySegmentation, SegEarthOV3Grounder
from mga.io import load_manifest, write_jsonl
from mga.mask_ops import load_label_mask
from mga.models import ClaimRole, GroundingEvidence, SampleRecord
from mga.scoring import MGAV2Scorer


@dataclass
class SceneBatch:
    sample_id: str
    pre_image: str
    post_image: str
    change_mask: str
    records: list[SampleRecord]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--max-scenes", type=int, default=10)
    parser.add_argument(
        "--vendor-root", default="/root/autodl-tmp/third_party/SegEarth-OV-3"
    )
    parser.add_argument("--checkpoint")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--logit-threshold", type=float, default=0.10)
    parser.add_argument("--query-expansion", default="remote-sensing")
    parser.add_argument(
        "--extra-entities",
        nargs="*",
        default=("building", "road"),
        help="Always segment these entities even when the claim parser misses them",
    )
    return parser


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "entity"


def _color(entity: str) -> tuple[int, int, int]:
    normalized = entity.lower()
    if normalized in {"building", "buildings", "house", "houses", "villa"}:
        return (239, 83, 80)
    if normalized in {"road", "roads", "street", "roadway"}:
        return (66, 133, 244)
    if normalized in {"tree", "trees", "vegetation", "forest", "woodland"}:
        return (52, 168, 83)
    return (251, 188, 4)


def _load_rgb(path: str | Path) -> Image.Image:
    with Image.open(path) as source:
        return source.convert("RGB")


def _overlay(
    image: Image.Image, results: dict[str, EntitySegmentation]
) -> Image.Image:
    blended = np.asarray(image, dtype=np.float32).copy()
    for entity, result in results.items():
        color = np.asarray(_color(entity), dtype=np.float32)
        blended[result.mask] = blended[result.mask] * 0.55 + color * 0.45
    output = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(output)
    y = 8
    shown: set[tuple[int, int, int]] = set()
    for entity in results:
        color = _color(entity)
        if color in shown:
            continue
        shown.add(color)
        label = {
            (239, 83, 80): "building/house",
            (66, 133, 244): "road",
            (52, 168, 83): "tree/vegetation",
        }.get(color, entity)
        draw.rectangle((8, y, 22, y + 14), fill=color, outline=(255, 255, 255))
        draw.text((28, y), label, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        y += 20
    return output


def _reference_overlay(
    image: Image.Image, label_mask: np.ndarray, class_map: dict[str, Any]
) -> Image.Image:
    blended = np.asarray(image, dtype=np.float32).copy()
    for raw_label, name in class_map.items():
        label = int(raw_label)
        if label == 0:
            continue
        color = np.asarray(_color(str(name)), dtype=np.float32)
        selected = label_mask == label
        blended[selected] = blended[selected] * 0.35 + color * 0.65
    output = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(output)
    draw.text(
        (8, 8),
        "reference change",
        fill=(255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )
    return output


def _panel(images: list[tuple[str, Image.Image]]) -> Image.Image:
    width = max(image.width for _label, image in images)
    height = max(image.height for _label, image in images)
    canvas = Image.new("RGB", (width * len(images), height + 28), color=(20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    for index, (label, image) in enumerate(images):
        x = index * width
        canvas.paste(image, (x, 28))
        draw.text((x + 8, 7), label, fill=(255, 255, 255))
    return canvas


def _scenes(records: list[SampleRecord], limit: int) -> list[SceneBatch]:
    grouped: dict[tuple[str, str, str, str], SceneBatch] = {}
    for record in records:
        key = (record.sample_id, record.pre_image, record.post_image, record.change_mask)
        if key not in grouped:
            grouped[key] = SceneBatch(*key, records=[])
        grouped[key].records.append(record)
    return list(grouped.values())[:limit]


def _entities(
    scene: SceneBatch, extra_entities: list[str] | tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                claim.entity.strip().lower()
                for record in scene.records
                for claim in record.claims
                if claim.role != ClaimRole.NO_CHANGE
                and claim.entity.strip()
                and claim.entity.strip().lower() != "scene"
            }
            | {entity.strip().lower() for entity in extra_entities if entity.strip()}
        )
    )


def _save_segmentations(
    scene_dir: Path,
    phase: str,
    image: Image.Image,
    results: dict[str, EntitySegmentation],
) -> tuple[Image.Image, list[dict[str, Any]]]:
    phase_dir = scene_dir / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for entity, result in results.items():
        mask_path = phase_dir / f"{_slug(entity)}.png"
        Image.fromarray(result.mask.astype(np.uint8) * 255).save(mask_path)
        rows.append(
            {
                "entity": entity,
                "queries": list(result.queries),
                "confidence": result.confidence,
                "presence_scores": list(result.presence_scores),
                "instance_count": result.instance_count,
                "mask_pixels": int(result.mask.sum()),
                "mask_fraction": float(result.mask.mean()),
                "mask_path": str(mask_path.resolve()),
            }
        )
    overlay = _overlay(image, results)
    overlay.save(scene_dir / f"{phase}_multi_entity_overlay.png")
    return overlay, rows


def _evidence(
    entity: str,
    pre: dict[str, EntitySegmentation],
    post: dict[str, EntitySegmentation],
    backend_id: str,
) -> GroundingEvidence:
    pre_result = pre[entity]
    post_result = post[entity]
    return GroundingEvidence(
        pre_mask=pre_result.mask,
        post_mask=post_result.mask,
        pre_confidence=pre_result.confidence,
        post_confidence=post_result.confidence,
        backend=backend_id,
        metadata={
            "entity": entity,
            "queries": list(pre_result.queries),
            "pre_instances": pre_result.instance_count,
            "post_instances": post_result.instance_count,
            "pre_presence_scores": list(pre_result.presence_scores),
            "post_presence_scores": list(post_result.presence_scores),
            "batch_precomputed": True,
        },
    )


def _mean(values: list[float | None]) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    return float(sum(concrete) / len(concrete)) if concrete else None


def _summary(score_rows: list[dict[str, Any]], elapsed: float, peak_mib: float) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    entity_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    for row in score_rows:
        by_model[row["model"]].append(row["score"])
        claims = {claim["claim_id"]: claim for claim in row["claims"]}
        for claim_score in row["score"]["claim_scores"]:
            statuses[claim_score["status"]] += 1
            claim = claims[claim_score["claim_id"]]
            entity_rows[claim["entity"]].append(claim_score)

    metric_names = ("faithfulness", "coverage", "temporal", "overall", "unverifiable_rate")
    model_summary = {}
    for model, rows in sorted(by_model.items()):
        model_summary[model] = {
            "captions": len(rows),
            **{metric: _mean([row[metric] for row in rows]) for metric in metric_names},
        }
    entity_summary = {}
    for entity, rows in sorted(entity_rows.items()):
        entity_summary[entity] = {
            "claims": len(rows),
            "faithfulness": _mean([row["faithfulness"] for row in rows]),
            "spatial_support": _mean([row["spatial_support"] for row in rows]),
            "temporal_support": _mean([row["temporal_support"] for row in rows]),
            "grounding_confidence": _mean([row["grounding_confidence"] for row in rows]),
            "statuses": dict(Counter(row["status"] for row in rows)),
        }
    ranked = sorted(
        (
            {
                "sample_id": row["sample_id"],
                "model": row["model"],
                "overall": row["score"]["overall"],
            }
            for row in score_rows
        ),
        key=lambda item: item["overall"] if item["overall"] is not None else -1.0,
    )
    return {
        "captions": len(score_rows),
        "elapsed_seconds": elapsed,
        "peak_gpu_memory_mib": peak_mib,
        "by_model": model_summary,
        "by_entity": entity_summary,
        "claim_statuses": dict(statuses),
        "lowest_overall": ranked[:10],
    }


def main() -> int:
    args = build_parser().parse_args()
    records = load_manifest(args.manifest)
    scenes = _scenes(records, args.max_scenes)
    if not scenes:
        raise ValueError("No scenes found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cache = EvidenceCache(args.cache_dir)

    started = time.perf_counter()
    grounder = SegEarthOV3Grounder(
        vendor_root=args.vendor_root,
        checkpoint_path=args.checkpoint,
        device=args.device,
        confidence_threshold=args.confidence_threshold,
        logit_threshold=args.logit_threshold,
        query_expansion=args.query_expansion,
    )
    if args.device.startswith("cuda"):
        grounder._torch.cuda.reset_peak_memory_stats()
    scorer = MGAV2Scorer()
    segmentation_rows = []
    score_rows = []

    for scene_index, scene in enumerate(scenes, start=1):
        scene_started = time.perf_counter()
        entities = _entities(scene, args.extra_entities)
        if not entities:
            continue
        pre_results = grounder.segment_queries(scene.pre_image, entities)
        post_results = grounder.segment_queries(scene.post_image, entities)
        scene_dir = args.output_dir / "scenes" / _slug(scene.sample_id)
        scene_dir.mkdir(parents=True, exist_ok=True)
        pre_image = _load_rgb(scene.pre_image)
        post_image = _load_rgb(scene.post_image)
        pre_overlay, pre_rows = _save_segmentations(
            scene_dir, "A", pre_image, pre_results
        )
        post_overlay, post_rows = _save_segmentations(
            scene_dir, "B", post_image, post_results
        )
        label_mask = load_label_mask(scene.change_mask)
        class_map = dict(scene.records[0].metadata.get("mask_class_map", {}))
        reference = _reference_overlay(post_image, label_mask, class_map)
        reference.save(scene_dir / "reference_change_overlay.png")
        overview_path = scene_dir / "overview_A_B_reference.png"
        _panel(
            [
                ("A: SegEarth entities", pre_overlay),
                ("B: SegEarth entities", post_overlay),
                ("Ground-truth change", reference),
            ]
        ).save(overview_path)

        for record in scene.records:
            evidence_by_claim = {}
            for claim in record.claims:
                if claim.role == ClaimRole.NO_CHANGE or claim.entity == "scene":
                    evidence = GroundingEvidence(backend=grounder.backend_id)
                else:
                    entity = claim.entity.strip().lower()
                    evidence = _evidence(
                        entity, pre_results, post_results, grounder.backend_id
                    )
                evidence_by_claim[claim.claim_id] = evidence
                key = cache.key(grounder.backend_id, record, claim)
                cache.save(key, evidence)

            score = scorer.score(record, label_mask, evidence_by_claim)
            score_rows.append(
                {
                    "sample_id": record.sample_id,
                    "model": record.model,
                    "dataset": record.dataset,
                    "caption": record.caption,
                    "claims": [claim.to_dict() for claim in record.claims],
                    "score": score.to_dict(),
                    "visualization": str(overview_path.resolve()),
                }
            )

        segmentation_rows.append(
            {
                "scene_index": scene_index,
                "sample_id": scene.sample_id,
                "entities": list(entities),
                "pre_image": scene.pre_image,
                "post_image": scene.post_image,
                "change_mask": scene.change_mask,
                "A": pre_rows,
                "B": post_rows,
                "overview": str(overview_path.resolve()),
                "elapsed_seconds": time.perf_counter() - scene_started,
            }
        )
        print(
            f"[{scene_index}/{len(scenes)}] {scene.sample_id}: "
            f"entities={','.join(entities)}"
        )

    elapsed = time.perf_counter() - started
    peak_mib = (
        grounder._torch.cuda.max_memory_allocated() / (1024**2)
        if args.device.startswith("cuda")
        else 0.0
    )
    write_jsonl(args.output_dir / "segmentations.jsonl", segmentation_rows)
    write_jsonl(args.output_dir / "mga_scores.jsonl", score_rows)
    summary = {
        "manifest": str(args.manifest.resolve()),
        "backend": grounder.backend_id,
        "scenes": len(segmentation_rows),
        **_summary(score_rows, elapsed, peak_mib),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
