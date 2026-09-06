"""Run an MGA CLI that expects ``--class-map`` using a JSON file.

This small adapter keeps long JSON mappings out of SSH command lines, where
PowerShell and remote-shell quoting can otherwise alter the payload.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--class-map-file", type=Path, required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    mapping = json.loads(args.class_map_file.read_text(encoding="utf-8"))
    class_map = json.dumps(mapping, ensure_ascii=True, separators=(",", ":"))
    forwarded = list(args.arguments)
    if forwarded and forwarded[0] == "--":
        forwarded.pop(0)
    sys.argv = [str(args.script), *forwarded, "--class-map", class_map]
    runpy.run_path(str(args.script), run_name="__main__")


if __name__ == "__main__":
    main()
