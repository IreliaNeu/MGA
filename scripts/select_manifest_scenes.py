"""Select a deterministic scene subset while retaining every model row."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-scenes", required=True, type=int)
    args = parser.parse_args()
    if args.max_scenes <= 0:
        raise ValueError("--max-scenes must be positive")

    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    scene_ids = sorted({str(row["sample_id"]) for row in rows})[: args.max_scenes]
    selected = [row for row in rows if str(row["sample_id"]) in set(scene_ids)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected)
    args.output.write_text(payload, encoding="utf-8")
    summary = {
        "selection_policy": "first N sample IDs after deterministic lexical sorting",
        "requested_scenes": args.max_scenes,
        "selected_scenes": len(scene_ids),
        "rows": len(selected),
        "models": dict(sorted(Counter(str(row.get("model")) for row in selected).items())),
        "first_sample_id": scene_ids[0] if scene_ids else None,
        "last_sample_id": scene_ids[-1] if scene_ids else None,
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }
    args.output.with_suffix(args.output.suffix + ".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
