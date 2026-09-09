"""List RGB colors and pixel counts from a sample of semantic maps."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument("--limit-per-dir", type=int, default=25)
    args = parser.parse_args()

    counts: Counter[tuple[int, int, int]] = Counter()
    file_count = 0
    for directory in args.directories:
        for path in sorted(directory.glob("*.png"))[: args.limit_per_dir]:
            with Image.open(path) as image:
                rgb = np.asarray(image.convert("RGB"))
            colors, color_counts = np.unique(
                rgb.reshape(-1, 3),
                axis=0,
                return_counts=True,
            )
            counts.update(
                {
                    tuple(int(channel) for channel in color): int(count)
                    for color, count in zip(colors, color_counts, strict=True)
                }
            )
            file_count += 1
    report = {
        "file_count": file_count,
        "colors": [
            {"rgb": list(color), "pixels": pixels}
            for color, pixels in counts.most_common()
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
