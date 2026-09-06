"""Apply final connector cleanup to the generated MGA Draw.io diagram."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tree = ET.parse(args.input)
    edge = tree.find(".//mxCell[@id='e_delta_components']")
    if edge is None:
        raise RuntimeError("Expected edge e_delta_components was not found")

    edge.set("id", "e_delta_relation")
    edge.set("target", "relation")
    style = edge.get("style", "")
    style = style.replace("exitX=1;exitY=0.3", "exitX=1;exitY=0.5")
    style = style.replace("entryX=0;entryY=0.3", "entryX=0;entryY=0.5")
    edge.set("style", style)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="utf-8", xml_declaration=True)
    print(args.output)


if __name__ == "__main__":
    main()
