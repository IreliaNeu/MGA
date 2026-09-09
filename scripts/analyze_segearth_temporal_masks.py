"""Compare SegEarth A/B mask differences with a class-id change mask."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-dir", required=True, type=Path)
    parser.add_argument("--post-dir", required=True, type=Path)
    parser.add_argument("--reference-mask", required=True, type=Path)
    parser.add_argument("--reference-image", type=Path)
    parser.add_argument("--image-stem", required=True)
    parser.add_argument(
        "--entity-label",
        required=True,
        nargs="+",
        help="Mappings such as road=1 building=2",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def _load_binary(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        return np.asarray(source.convert("L")) > 0


def _metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | int]:
    true_positive = int(np.logical_and(prediction, target).sum())
    false_positive = int(np.logical_and(prediction, ~target).sum())
    false_negative = int(np.logical_and(~prediction, target).sum())
    union = true_positive + false_positive + false_negative
    return {
        "true_positive_pixels": true_positive,
        "false_positive_pixels": false_positive,
        "false_negative_pixels": false_negative,
        "iou": true_positive / union if union else 1.0,
        "precision": true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0,
        "recall": true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0,
    }


def _error_map(
    prediction: np.ndarray, target: np.ndarray, reference_image: Path | None
) -> Image.Image:
    height, width = prediction.shape
    if reference_image:
        with Image.open(reference_image) as source:
            background = np.asarray(source.convert("RGB"), dtype=np.float32)
        background = np.asarray(
            Image.fromarray(background.astype(np.uint8)).resize((width, height)),
            dtype=np.float32,
        )
        output = background * 0.40
    else:
        output = np.full((height, width, 3), 50, dtype=np.float32)

    true_positive = np.logical_and(prediction, target)
    false_positive = np.logical_and(prediction, ~target)
    false_negative = np.logical_and(~prediction, target)
    output[true_positive] = (52, 200, 90)
    output[false_positive] = (239, 83, 80)
    output[false_negative] = (66, 133, 244)
    image = Image.fromarray(np.clip(output, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    legend = (
        ("TP", (52, 200, 90)),
        ("FP", (239, 83, 80)),
        ("FN", (66, 133, 244)),
    )
    x, y = 8, 8
    for label, color in legend:
        draw.rectangle((x, y, x + 14, y + 14), fill=color, outline=(255, 255, 255))
        draw.text((x + 20, y), label, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        y += 20
    return image


def main() -> int:
    args = build_parser().parse_args()
    mappings = {}
    for value in args.entity_label:
        entity, separator, label = value.partition("=")
        if not separator:
            raise ValueError(f"Invalid entity-label mapping: {value}")
        mappings[entity.strip()] = int(label)

    with Image.open(args.reference_mask) as source:
        reference = np.asarray(source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for entity, label in mappings.items():
        pre_path = args.pre_dir / f"{args.image_stem}__{entity}.png"
        post_path = args.post_dir / f"{args.image_stem}__{entity}.png"
        pre = _load_binary(pre_path)
        post = _load_binary(post_path)
        predicted_change = np.logical_xor(pre, post)
        target = reference == label
        metrics = _metrics(predicted_change, target)

        predicted_path = args.output_dir / f"{entity}__predicted_change.png"
        Image.fromarray(predicted_change.astype(np.uint8) * 255).save(predicted_path)
        error_path = args.output_dir / f"{entity}__tp_fp_fn.png"
        _error_map(predicted_change, target, args.reference_image).save(error_path)
        rows.append(
            {
                "entity": entity,
                "reference_label": label,
                "pre_mask_pixels": int(pre.sum()),
                "post_mask_pixels": int(post.sum()),
                "predicted_change_pixels": int(predicted_change.sum()),
                **metrics,
                "predicted_change_path": str(predicted_path.resolve()),
                "error_map_path": str(error_path.resolve()),
            }
        )

    report = {
        "reference_mask": str(args.reference_mask.resolve()),
        "temporal_operator": "xor",
        "entities": rows,
    }
    report_path = args.output_dir / "temporal_mask_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
