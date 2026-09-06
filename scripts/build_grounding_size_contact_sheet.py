"""Build one overview sheet comparing Tiny and Base Grounding DINO boxes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _combined_by_source(report: dict) -> dict[str, Path]:
    return {
        row["image"]: Path(row["combined_visualization_path"])
        for row in report["images"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--tiny-report", required=True, type=Path)
    parser.add_argument("--base-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    selection = _load(args.selection)
    tiny = _combined_by_source(_load(args.tiny_report))
    base = _combined_by_source(_load(args.base_report))
    columns = (
        ("Tiny / pre", "pre_image", tiny),
        ("Base / pre", "pre_image", base),
        ("Tiny / post", "post_image", tiny),
        ("Base / post", "post_image", base),
    )
    tile = 256
    header = 32
    label = 42
    sheet = Image.new(
        "RGB", (tile * len(columns), header + (tile + label) * len(selection)), "white"
    )
    draw = ImageDraw.Draw(sheet)
    for column, (title, _, _) in enumerate(columns):
        draw.text((column * tile + 8, 8), title, fill="black")
    for row_index, item in enumerate(selection):
        y = header + row_index * (tile + label)
        for column, (_, image_key, lookup) in enumerate(columns):
            source = item[image_key]
            with Image.open(lookup[source]) as image:
                sheet.paste(image.convert("RGB").resize((tile, tile)), (column * tile, y))
        text = (
            f"{item['sample_id']} | {item['case']} | {item['entity']} | "
            f"Tiny={item['tiny_mean_fraction']:.3f}, Base={item['base_mean_fraction']:.3f}"
        )
        draw.text((8, y + tile + 10), text, fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
