"""Render multi-entity SegEarth masks beside bitemporal semantic ground truth."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from mga.semantic_change import load_label_ids

COLORS = (
    (238, 180, 34),
    (218, 70, 70),
    (56, 168, 87),
    (60, 116, 210),
    (160, 92, 200),
    (35, 174, 174),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--class-map-file", type=Path, required=True)
    parser.add_argument("--max-scenes", type=int, default=0)
    parser.add_argument("--overview-limit", type=int, default=24)
    args = parser.parse_args()

    class_names = {
        int(key): str(value)
        for key, value in json.loads(
            args.class_map_file.read_text(encoding="utf-8")
        ).items()
    }
    color_by_entity = {
        entity: COLORS[index % len(COLORS)]
        for index, entity in enumerate(class_names.values())
    }
    grouped: dict[str, list[dict]] = defaultdict(list)
    for line in args.samples.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            grouped[str(item["sample_id"])].append(item)

    scene_ids = sorted(grouped)
    if args.max_scenes > 0:
        scene_ids = scene_ids[: args.max_scenes]
    per_scene_dir = args.output_dir / "per_scene"
    per_scene_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    missing = []
    for sample_id in scene_ids:
        item = grouped[sample_id][0]
        cache_path = args.cache_dir / f"{sample_id}.npz"
        if not cache_path.is_file():
            missing.append(sample_id)
            continue
        path = render_scene(
            item=item,
            cache_path=cache_path,
            output_path=per_scene_dir / f"{sample_id}.png",
            class_names=class_names,
            color_by_entity=color_by_entity,
        )
        rendered.append(path)

    overview_path = args.output_dir / "overview.png"
    render_overview(rendered[: args.overview_limit], overview_path)
    manifest = {
        "requested_scene_count": len(scene_ids),
        "rendered_scene_count": len(rendered),
        "missing_cache_count": len(missing),
        "per_scene_dir": str(per_scene_dir),
        "overview": str(overview_path),
        "class_colors": {
            entity: list(color) for entity, color in color_by_entity.items()
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def render_scene(
    *,
    item: dict,
    cache_path: Path,
    output_path: Path,
    class_names: dict[int, str],
    color_by_entity: dict[str, tuple[int, int, int]],
) -> Path:
    pre = Image.open(item["pre_image"]).convert("RGB")
    post = Image.open(item["post_image"]).convert("RGB")
    width, height = pre.size
    with np.load(cache_path, allow_pickle=False) as cache:
        entities = json.loads(str(cache["entities_json"].item()))
        pre_masks = cache["pre_masks"].astype(bool)
        post_masks = cache["post_masks"].astype(bool)

    gt_pre = load_label_ids(item["pre_label"])
    gt_post = load_label_ids(item["post_label"])
    panels = (
        ("T1 image", pre),
        ("T2 image", post),
        (
            "SegEarth T1 masks",
            overlay_masks(pre, entities, pre_masks, color_by_entity),
        ),
        (
            "SegEarth T2 masks",
            overlay_masks(post, entities, post_masks, color_by_entity),
        ),
        (
            "Semantic GT T1",
            overlay_semantic(pre, gt_pre, class_names, color_by_entity),
        ),
        (
            "Semantic GT T2",
            overlay_semantic(post, gt_post, class_names, color_by_entity),
        ),
    )
    title_height = 32
    legend_height = 34
    canvas = Image.new(
        "RGB",
        (width * 3, (height + title_height) * 2 + legend_height),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, panel) in enumerate(panels):
        column = index % 3
        row = index // 3
        x = column * width
        y = row * (height + title_height)
        canvas.paste(panel, (x, y + title_height))
        draw.text((x + 8, y + 9), label, fill="black", font=font)

    legend_y = (height + title_height) * 2 + 10
    cursor_x = 8
    for entity, color in color_by_entity.items():
        draw.rectangle(
            (cursor_x, legend_y, cursor_x + 14, legend_y + 14),
            fill=color,
        )
        draw.text((cursor_x + 19, legend_y + 1), entity, fill="black", font=font)
        cursor_x += 28 + 8 * len(entity)
    draw.text(
        (max(cursor_x, width * 3 - 180), legend_y + 1),
        str(item["sample_id"]),
        fill=(70, 70, 70),
        font=font,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, optimize=True)
    return output_path


def overlay_masks(
    image: Image.Image,
    entities: list[str],
    masks: np.ndarray,
    color_by_entity: dict[str, tuple[int, int, int]],
) -> Image.Image:
    base = np.asarray(image).astype(np.float32)
    output = base.copy()
    for entity, mask in zip(entities, masks, strict=False):
        color = np.asarray(color_by_entity.get(entity, (255, 255, 255)))
        output[mask] = output[mask] * 0.45 + color * 0.55
    return Image.fromarray(np.clip(output, 0, 255).astype(np.uint8))


def overlay_semantic(
    image: Image.Image,
    labels: np.ndarray,
    class_names: dict[int, str],
    color_by_entity: dict[str, tuple[int, int, int]],
) -> Image.Image:
    base = np.asarray(image).astype(np.float32)
    output = base.copy()
    for class_id, entity in class_names.items():
        mask = labels == class_id
        color = np.asarray(color_by_entity[entity])
        output[mask] = output[mask] * 0.35 + color * 0.65
    return Image.fromarray(np.clip(output, 0, 255).astype(np.uint8))


def render_overview(paths: list[Path], output_path: Path) -> None:
    if not paths:
        Image.new("RGB", (512, 256), "white").save(output_path)
        return
    thumbnails = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((480, 350))
        thumbnails.append(image.copy())
    columns = 3
    rows = (len(thumbnails) + columns - 1) // columns
    cell_width = max(item.width for item in thumbnails) + 12
    cell_height = max(item.height for item in thumbnails) + 12
    overview = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        (238, 238, 238),
    )
    for index, image in enumerate(thumbnails):
        x = (index % columns) * cell_width + 6
        y = (index // columns) * cell_height + 6
        overview.paste(image, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overview.save(output_path, optimize=True)


if __name__ == "__main__":
    main()
