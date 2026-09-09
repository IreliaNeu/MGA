"""Run native SegEarth-OV3 segmentation for one image and multiple entities."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from mga.grounding.segearth_ov3 import SegEarthOV3Grounder

COLORS = (
    (239, 83, 80),
    (66, 133, 244),
    (52, 168, 83),
    (251, 188, 4),
    (171, 71, 188),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--entities", required=True, nargs="+")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--vendor-root", default="/root/autodl-tmp/third_party/SegEarth-OV-3"
    )
    parser.add_argument("--checkpoint")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--logit-threshold", type=float, default=0.10)
    parser.add_argument("--query-expansion", default="remote-sensing")
    return parser


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "entity"


def _overlay(
    image: Image.Image,
    masks: list[tuple[str, np.ndarray, tuple[int, int, int]]],
) -> Image.Image:
    blended = np.asarray(image.convert("RGB"), dtype=np.float32).copy()
    for _entity, mask, color in masks:
        blended[mask] = blended[mask] * 0.55 + np.asarray(color, dtype=np.float32) * 0.45
    output = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(output)
    x, y = 8, 8
    for entity, _mask, color in masks:
        draw.rectangle((x, y, x + 14, y + 14), fill=color, outline=(255, 255, 255))
        draw.text((x + 20, y), entity, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        y += 20
    return output


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    grounder = SegEarthOV3Grounder(
        vendor_root=args.vendor_root,
        checkpoint_path=args.checkpoint,
        device=args.device,
        confidence_threshold=args.confidence_threshold,
        logit_threshold=args.logit_threshold,
        query_expansion=args.query_expansion,
    )
    loaded_at = time.perf_counter()
    if args.device.startswith("cuda"):
        grounder._torch.cuda.reset_peak_memory_stats()
    results = grounder.segment_queries(args.image, args.entities)
    finished_at = time.perf_counter()

    with Image.open(args.image) as source:
        source_image = source.convert("RGB")
    rows = []
    overlays = []
    for index, (entity, result) in enumerate(results.items()):
        color = COLORS[index % len(COLORS)]
        output_path = args.output_dir / f"{args.image.stem}__{_slug(entity)}.png"
        Image.fromarray(np.asarray(result.mask, dtype=np.uint8) * 255).save(output_path)
        overlay_path = args.output_dir / f"{args.image.stem}__{_slug(entity)}__overlay.png"
        _overlay(source_image, [(entity, result.mask, color)]).save(overlay_path)
        overlays.append((entity, result.mask, color))
        rows.append(
            {
                "entity": entity,
                "queries": list(result.queries),
                "confidence": result.confidence,
                "presence_scores": list(result.presence_scores),
                "instance_count": result.instance_count,
                "mask_pixels": int(result.mask.sum()),
                "mask_fraction": float(result.mask.mean()),
                "mask_path": str(output_path.resolve()),
                "overlay_path": str(overlay_path.resolve()),
            }
        )

    combined_overlay = args.output_dir / f"{args.image.stem}__combined_overlay.png"
    _overlay(source_image, overlays).save(combined_overlay)
    report = {
        "backend": grounder.backend_id,
        "image": str(args.image.resolve()),
        "model_load_seconds": loaded_at - started,
        "inference_seconds": finished_at - loaded_at,
        "peak_gpu_memory_mib": (
            grounder._torch.cuda.max_memory_allocated() / (1024**2)
            if args.device.startswith("cuda")
            else None
        ),
        "combined_overlay_path": str(combined_overlay.resolve()),
        "entities": rows,
    }
    report_path = args.output_dir / f"{args.image.stem}__report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
