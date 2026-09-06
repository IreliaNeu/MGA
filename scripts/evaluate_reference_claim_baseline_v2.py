"""Compute a transparent reference-dependent canonical Claim-F1 baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mga.parsing import HeuristicClaimParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=("Draft", "Refined"))
    return parser


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def atoms(claim_parser: HeuristicClaimParser, text: str, *, with_location: bool) -> set[tuple]:
    result = set()
    for claim in claim_parser.parse(text):
        atom = (claim.entity, claim.change_type.value, claim.role.value)
        if with_location:
            atom = (*atom, str(claim.location) if claim.location else None)
        result.add(atom)
    return result


def f1(candidate: set[tuple], reference: set[tuple]) -> float:
    if not candidate and not reference:
        return 1.0
    if not candidate or not reference:
        return 0.0
    overlap = len(candidate & reference)
    precision = overlap / len(candidate)
    recall = overlap / len(reference)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    claim_parser = HeuristicClaimParser()
    selected = sorted(
        (row for row in read_jsonl(args.manifest) if row["model"] in args.models),
        key=lambda row: (row["model"], row["sample_id"]),
    )
    sample_rows = []
    for row in selected:
        candidate = atoms(claim_parser, row["caption"], with_location=False)
        candidate_location = atoms(claim_parser, row["caption"], with_location=True)
        reference_atoms = [
            atoms(claim_parser, reference, with_location=False)
            for reference in row["references"]
        ]
        reference_location_atoms = [
            atoms(claim_parser, reference, with_location=True)
            for reference in row["references"]
        ]
        sample_rows.append(
            {
                "sample_id": row["sample_id"],
                "model": row["model"],
                "Reference-Claim-F1": max(
                    f1(candidate, reference) for reference in reference_atoms
                ),
                "Reference-Claim-Location-F1": max(
                    f1(candidate_location, reference)
                    for reference in reference_location_atoms
                ),
                "candidate_claim_count": len(candidate),
            }
        )

    summary = {
        "protocol": "reference-canonical-claim-f1-v1",
        "parser": "MGA HeuristicClaimParser (same version as candidate scoring)",
        "reference_aggregation": "maximum F1 over the five official references",
        "models": {},
        "interpretation": (
            "internal text-only control; depends on reference captions, has no image evidence, "
            "and is not presented as a published factuality baseline"
        ),
    }
    for model in args.models:
        rows = [row for row in sample_rows if row["model"] == model]
        summary["models"][model] = {
            "count": len(rows),
            "Reference-Claim-F1": (
                sum(row["Reference-Claim-F1"] for row in rows) / len(rows)
            ),
            "Reference-Claim-Location-F1": (
                sum(row["Reference-Claim-Location-F1"] for row in rows) / len(rows)
            ),
            "mean_candidate_claim_count": (
                sum(row["candidate_claim_count"] for row in rows) / len(rows)
            ),
        }
    (args.output_dir / "reference_claim_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(args.output_dir / "reference_claim_samples.jsonl", sample_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
