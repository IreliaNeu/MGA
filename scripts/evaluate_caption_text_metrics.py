"""Evaluate Draft/Refined captions with official LEVIR-CC metric implementations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--official-repository", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=("Draft", "Refined"))
    parser.add_argument('--skip-meteor', action='store_true')
    return parser


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.official_repository.resolve()))
    from eval_func.bleu.bleu import Bleu
    from eval_func.cider.cider import Cider
    from eval_func.meteor.meteor import Meteor
    from eval_func.rouge.rouge import Rouge

    rows = read_jsonl(args.manifest)
    summary = {
        "scope": "project-recomputed Draft/Refined on the aligned 1000-scene LEVIR-MCI subset",
        "implementation": str(args.official_repository.resolve()),
        "models": {},
    }
    sample_rows = []
    for model in args.models:
        selected = sorted(
            (row for row in rows if row["model"] == model), key=lambda row: row["sample_id"]
        )
        if len(selected) != 1000:
            raise ValueError(f"Expected 1000 rows for {model}, got {len(selected)}")
        references = [row["references"] for row in selected]
        hypotheses = [[row["caption"]] for row in selected]
        bleu_score, bleu_rows = Bleu(4).compute_score(references, hypotheses)
        rouge_score, rouge_rows = Rouge().compute_score(references, hypotheses)
        cider_score, cider_rows = Cider().compute_score(references, hypotheses)
        meteor_score, meteor_rows = (None, [None] * len(selected)) if args.skip_meteor else Meteor().compute_score(references, hypotheses)
        summary["models"][model] = {
            "count": len(selected),
            "BLEU-1": float(bleu_score[0]),
            "BLEU-2": float(bleu_score[1]),
            "BLEU-3": float(bleu_score[2]),
            "BLEU-4": float(bleu_score[3]),
            "METEOR": float(meteor_score),
            "ROUGE-L": float(rouge_score),
            "CIDEr": float(cider_score),
        }
        for index, row in enumerate(selected):
            sample_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "model": model,
                    "BLEU-1": float(bleu_rows[0][index]),
                    "BLEU-4": float(bleu_rows[3][index]),
                    "METEOR": float(meteor_rows[index]),
                    "ROUGE-L": float(rouge_rows[index]),
                    "CIDEr": float(cider_rows[index]),
                }
            )
    (args.output_dir / "metric_baseline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (args.output_dir / "metric_baseline_samples.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for row in sample_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
