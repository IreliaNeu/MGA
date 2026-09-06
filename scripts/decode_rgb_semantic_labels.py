"""Decode aligned RGB semantic labels for the generic fact-graph pipeline."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mga.semantic_palette import decode_label_file, load_rgb_palette


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-dir", type=Path, required=True)
    parser.add_argument("--post-dir", type=Path, required=True)
    parser.add_argument("--output-pre-dir", type=Path, required=True)
    parser.add_argument("--output-post-dir", type=Path, required=True)
    parser.add_argument("--palette-file", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--unknown-class", type=int)
    args = parser.parse_args()

    palette = load_rgb_palette(args.palette_file)
    names = sorted(path.name for path in args.pre_dir.glob("*.png"))
    if args.limit > 0:
        names = names[: args.limit]
    missing = [name for name in names if not (args.post_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing aligned post labels: {missing[:12]}")

    def process(name: str) -> str:
        decode_label_file(
            args.pre_dir / name,
            args.output_pre_dir / name,
            palette,
            unknown_class=args.unknown_class,
        )
        decode_label_file(
            args.post_dir / name,
            args.output_post_dir / name,
            palette,
            unknown_class=args.unknown_class,
        )
        return name

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        completed = 0
        for _ in executor.map(process, names):
            completed += 1
            if completed % 100 == 0 or completed == len(names):
                print(f"decoded {completed}/{len(names)} pairs", flush=True)
    print(
        json.dumps(
            {
                "pair_count": len(names),
                "output_pre_dir": str(args.output_pre_dir),
                "output_post_dir": str(args.output_post_dir),
            }
        )
    )


if __name__ == "__main__":
    main()
