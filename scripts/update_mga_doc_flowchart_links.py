"""Point the MGA calculation note at the final cleaned figure exports."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.document.read_text(encoding="utf-8")
    replacements = {
        "paper/figures/mga_three_mode_flow.drawio": (
            "paper/figures/mga_three_mode_flow_clean.drawio"
        ),
        "paper/figures/mga_three_mode_flow.svg": (
            "paper/figures/mga_three_mode_flow_clean.svg"
        ),
        "paper/figures/mga_three_mode_flow.png": (
            "paper/figures/mga_three_mode_flow_clean.png"
        ),
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"Expected document link was not found: {old}")
        text = text.replace(old, new)
    args.document.write_text(text, encoding="utf-8", newline="\n")
    print(args.document)


if __name__ == "__main__":
    main()
