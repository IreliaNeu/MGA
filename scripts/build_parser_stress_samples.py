"""Create entity-surface stress samples without changing the reference claims."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SURFACE_FORMS = {
    "cropland": "cultivated fields",
    "road": "transportation corridors",
    "vegetation": "green cover",
    "building": "built structures",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    output = []
    for line in args.samples.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        caption = str(item["caption"])
        replacements = {}
        for claim in item["claims"]:
            entity = str(claim["entity"])
            surface = SURFACE_FORMS.get(entity)
            if surface:
                replacements[entity] = surface
        for entity, surface in sorted(
            replacements.items(), key=lambda value: len(value[0]), reverse=True
        ):
            caption = re.sub(
                rf"(?<!\w){re.escape(entity)}(?!\w)",
                surface,
                caption,
                flags=re.IGNORECASE,
            )
        item["caption"] = caption
        item["item_id"] = f"{item['item_id']}:surface-stress"
        item["sample_type"] = f"{item['sample_type']}_surface_stress"
        item["parser_surface_forms"] = replacements
        output.append(item)
        if args.limit > 0 and len(output) >= args.limit:
            break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in output:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output), "item_count": len(output)}))


if __name__ == "__main__":
    main()
