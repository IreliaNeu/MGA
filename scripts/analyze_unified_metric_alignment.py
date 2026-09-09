"""Join unified sample scores and report correlations plus Draft/Refined rankings."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from scipy.stats import kendalltau, spearmanr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-metrics", required=True, type=Path)
    parser.add_argument("--bertscore", required=True, type=Path)
    parser.add_argument("--spice", required=True, type=Path)
    parser.add_argument("--clipscore", required=True, type=Path)
    parser.add_argument("--reference-claim", required=True, type=Path)
    parser.add_argument("--hybrid", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def finite(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def merge_file(index: dict[tuple[str, str], dict], path: Path) -> None:
    for row in read_jsonl(path):
        key = (str(row["sample_id"]), str(row["model"]))
        index.setdefault(key, {"sample_id": key[0], "model": key[1]}).update(row)


def main() -> int:
    args = build_parser().parse_args()
    index: dict[tuple[str, str], dict] = {}
    for path in (
        args.text_metrics,
        args.bertscore,
        args.spice,
        args.clipscore,
        args.reference_claim,
    ):
        merge_file(index, path)
    for row in read_jsonl(args.hybrid):
        key = (str(row["sample_id"]), str(row["model"]))
        if key not in index:
            continue
        score = row["score"]
        index[key].update(
            {
                "MGA-Overall": score["overall"],
                "MGA-Faithfulness": score["faithfulness"],
                "MGA-Coverage": score["coverage"],
                "MGA-Temporal": score["temporal"],
                "MGA-Unverifiable": score["unverifiable_rate"],
            }
        )

    rows = [row for row in index.values() if row["model"] in {"Draft", "Refined"}]
    text_metrics = (
        "BLEU-1",
        "BLEU-4",
        "METEOR",
        "ROUGE-L",
        "CIDEr",
        "SPICE",
        "BERTScore-F1",
        "BiTemporal-CLIP-mean",
        "Reference-Claim-F1",
    )
    mga_metrics = (
        "MGA-Overall",
        "MGA-Faithfulness",
        "MGA-Coverage",
        "MGA-Temporal",
    )
    correlations = []
    for left in text_metrics:
        for right in mga_metrics:
            pairs = [
                (finite(row.get(left)), finite(row.get(right)))
                for row in rows
            ]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            left_values = [a for a, _b in pairs]
            right_values = [b for _a, b in pairs]
            rho, rho_p = spearmanr(left_values, right_values)
            tau, tau_p = kendalltau(left_values, right_values)
            correlations.append(
                {
                    "metric": left,
                    "mga_component": right,
                    "n": len(pairs),
                    "spearman_rho": finite(rho),
                    "spearman_p": finite(rho_p),
                    "kendall_tau": finite(tau),
                    "kendall_p": finite(tau_p),
                }
            )

    by_scene = defaultdict(dict)
    for row in rows:
        by_scene[row["sample_id"]][row["model"]] = row
    paired_rankings = {}
    for metric in (*text_metrics, *mga_metrics):
        draft_wins = refined_wins = ties = missing = 0
        deltas = []
        for scene_rows in by_scene.values():
            if set(scene_rows) != {"Draft", "Refined"}:
                missing += 1
                continue
            draft = finite(scene_rows["Draft"].get(metric))
            refined = finite(scene_rows["Refined"].get(metric))
            if draft is None or refined is None:
                missing += 1
            elif draft > refined:
                draft_wins += 1
                deltas.append(refined - draft)
            elif refined > draft:
                refined_wins += 1
                deltas.append(refined - draft)
            else:
                ties += 1
                deltas.append(0.0)
        paired_rankings[metric] = {
            "scenes": len(by_scene),
            "draft_wins": draft_wins,
            "refined_wins": refined_wins,
            "ties": ties,
            "missing": missing,
            "mean_refined_minus_draft": (
                sum(deltas) / len(deltas) if deltas else None
            ),
        }

    output = {
        "protocol": "unified-sample-level-alignment-v1",
        "scope": "Draft/Refined, aligned 1000 LEVIR-MCI scenes",
        "rows": len(rows),
        "correlations": correlations,
        "paired_rankings": paired_rankings,
        "caution": (
            "Inter-metric correlation is not human validity. Final claims still require "
            "independent human factuality judgments on a held-out test set."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
