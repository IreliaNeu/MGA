"""Analyze aligned human consensus and metric scores without fitting on test data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mga.human_validity import analyze, rater_agreement
from mga.io import read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--metric-specs", required=True, type=Path)
    parser.add_argument("--votes", type=Path, help="Optional pre-adjudication long-form JSONL")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", choices=("dev", "test", "pilot", "training"), default="test")
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; select a new versioned path")
    rows = list(read_jsonl(args.input))
    summary = analyze(
        rows,
        json.loads(args.metric_specs.read_text(encoding="utf-8")),
        split=args.split,
        replicates=args.replicates,
        seed=args.seed,
    )
    summary["inputs"] = {
        name: {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in (("aligned_consensus", args.input), ("metric_specs", args.metric_specs))
    }
    summary["rater_agreement"] = None
    if args.votes:
        summary["rater_agreement"] = rater_agreement(
            list(read_jsonl(args.votes)), rows, split=args.split
        )
        summary["inputs"]["votes"] = {
            "name": args.votes.name,
            "sha256": hashlib.sha256(args.votes.read_bytes()).hexdigest(),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output}; dimensions={len(summary['dimensions'])}; split={args.split}")


if __name__ == "__main__":
    main()
