"""Create configurable non-dictionary entity-surface stress samples."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--surface-map-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    surface_forms = {
        str(key): str(value)
        for key, value in json.loads(
            args.surface_map_file.read_text(encoding="utf-8")
        ).items()
    }
    output = []
    for line in args.samples.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        caption = str(item["caption"])
        replacements = {
            str(claim["entity"]): surface_forms[str(claim["entity"])]
            for claim in item["claims"]
            if str(claim["entity"]) in surface_forms
        }
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
