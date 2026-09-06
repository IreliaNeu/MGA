"""Render Grounding DINO boxes for raw, punctuated, or expanded prompts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from mga.grounding.hf_dino_expanded import ExpandedHFGroundingDinoGrounder
from mga.grounding.query_expansion import expand_grounding_queries, format_grounding_query

COLORS = (
    (239, 83, 80),
    (66, 133, 244),
    (52, 168, 83),
    (251, 188, 4),
    (171, 71, 188),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, nargs="+", type=Path)
    parser.add_argument("--entities", required=True, nargs="+")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--box-threshold", type=float, default=0.30)
    parser.add_argument("--text-threshold", type=float, default=0.25)
    parser.add_argument(
        "--query-mode", choices=("raw", "punctuated", "synonyms"), default="punctuated"
    )
    parser.add_argument("--query-expansion", default="remote-sensing")
    return parser


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "entity"


def _prompt(entity: str, mode: str, profile: str) -> str:
    if mode == "raw":
        return entity
    if mode == "punctuated":
        return format_grounding_query((entity,))
    return format_grounding_query(expand_grounding_queries(entity, profile))


def _detect(
    grounder: ExpandedHFGroundingDinoGrounder, image: Image.Image, prompt: str
) -> dict[str, Any]:
    inputs = grounder._processor(images=image, text=prompt, return_tensors="pt")
    inputs = {key: value.to(grounder.device) for key, value in inputs.items()}
    with grounder._torch.inference_mode():
        outputs = grounder._model(**inputs)
    kwargs = {
        "target_sizes": [image.size[::-1]],
        "box_threshold": grounder.box_threshold,
        "text_threshold": grounder.text_threshold,
    }
    try:
        results = grounder._processor.post_process_grounded_object_detection(
            outputs, inputs.get("input_ids"), **kwargs
        )
    except TypeError:
        results = grounder._processor.post_process_grounded_object_detection(
            outputs,
            inputs.get("input_ids"),
            target_sizes=kwargs["target_sizes"],
            threshold=grounder.box_threshold,
        )
    result = results[0]
    boxes = [[float(value) for value in box] for box in result.get("boxes", [])]
    scores = [float(value) for value in result.get("scores", [])]
    labels = result.get("text_labels", result.get("labels", []))
    labels = [str(value) for value in labels]
    return {"prompt": prompt, "boxes": boxes, "scores": scores, "labels": labels}


def _draw_boxes(
    image: Image.Image,
    detections: list[tuple[str, dict[str, Any], tuple[int, int, int]]],
) -> Image.Image:
    output = image.copy().convert("RGB")
    draw = ImageDraw.Draw(output)
    for entity, result, color in detections:
        for index, (box, score) in enumerate(zip(result["boxes"], result["scores"], strict=False)):
            x_min, y_min, x_max, y_max = box
            draw.rectangle((x_min, y_min, x_max, y_max), outline=color, width=3)
            detected_label = result["labels"][index] if index < len(result["labels"]) else entity
            label = f"{entity}/{detected_label} {score:.3f}"
            text_box = draw.textbbox((x_min, y_min), label, stroke_width=1)
            draw.rectangle(text_box, fill=(0, 0, 0))
            draw.text((x_min, y_min), label, fill=color, stroke_width=1, stroke_fill=(0, 0, 0))
    return output


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    grounder = ExpandedHFGroundingDinoGrounder(
        model_id=args.model,
        device=args.device,
        box_threshold=args.box_threshold,
        text_threshold=args.text_threshold,
        query_expansion=args.query_expansion,
    )
    report_rows = []
    for image_path in args.images:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        image_key = f"{_slug(image_path.parent.name)}_{image_path.stem}"
        detections = []
        entity_rows = []
        for index, entity in enumerate(args.entities):
            prompt = _prompt(entity, args.query_mode, args.query_expansion)
            result = _detect(grounder, image, prompt)
            color = COLORS[index % len(COLORS)]
            detections.append((entity, result, color))
            entity_path = args.output_dir / (
                f"{image_key}__{_slug(entity)}__{args.query_mode}__boxes.png"
            )
            _draw_boxes(image, [(entity, result, color)]).save(entity_path)
            entity_rows.append(
                {
                    "entity": entity,
                    **result,
                    "box_count": len(result["boxes"]),
                    "visualization_path": str(entity_path.resolve()),
                }
            )
        combined_path = args.output_dir / (
            f"{image_key}__{args.query_mode}__combined_boxes.png"
        )
        _draw_boxes(image, detections).save(combined_path)
        report_rows.append(
            {
                "image": str(image_path.resolve()),
                "combined_visualization_path": str(combined_path.resolve()),
                "entities": entity_rows,
            }
        )

    report = {
        "model": args.model,
        "query_mode": args.query_mode,
        "box_threshold": args.box_threshold,
        "text_threshold": args.text_threshold,
        "images": report_rows,
    }
    report_path = args.output_dir / f"grounding_dino__{args.query_mode}__report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
