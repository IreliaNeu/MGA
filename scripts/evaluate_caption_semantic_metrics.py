"""Evaluate Draft/Refined captions with BERTScore and official SPICE."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=("Draft", "Refined"))
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=("bertscore", "spice"),
        default=("bertscore", "spice"),
    )
    parser.add_argument("--bertscore-model", default="roberta-large")
    parser.add_argument("--bertscore-layers", type=int, default=17)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    return parser


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_bertscore(
    selected_by_model: dict[str, list[dict]],
    *,
    model_type: str,
    num_layers: int,
    batch_size: int,
    device: str,
) -> tuple[dict[str, dict], list[dict]]:
    from bert_score import score

    summaries: dict[str, dict] = {}
    sample_rows: list[dict] = []
    for model, selected in selected_by_model.items():
        candidates = [str(row["caption"]) for row in selected]
        references = [list(row["references"]) for row in selected]
        precision, recall, f1 = score(
            candidates,
            references,
            model_type=model_type,
            num_layers=num_layers,
            batch_size=batch_size,
            device=device,
            idf=False,
            rescale_with_baseline=False,
            verbose=True,
        )
        p_values = precision.cpu().tolist()
        r_values = recall.cpu().tolist()
        f_values = f1.cpu().tolist()
        summaries[model] = {
            "count": len(selected),
            "BERTScore-P": sum(p_values) / len(p_values),
            "BERTScore-R": sum(r_values) / len(r_values),
            "BERTScore-F1": sum(f_values) / len(f_values),
        }
        sample_rows.extend(
            {
                "sample_id": row["sample_id"],
                "model": model,
                "BERTScore-P": float(p_values[index]),
                "BERTScore-R": float(r_values[index]),
                "BERTScore-F1": float(f_values[index]),
            }
            for index, row in enumerate(selected)
        )
    return summaries, sample_rows


def run_spice(
    selected_by_model: dict[str, list[dict]],
) -> tuple[dict[str, dict], list[dict]]:
    from pycocoevalcap.spice.spice import Spice

    ground_truth: dict[int, list[str]] = {}
    results: dict[int, list[str]] = {}
    index_rows: dict[int, tuple[str, dict]] = {}
    item_index = 0
    for model, selected in selected_by_model.items():
        for row in selected:
            ground_truth[item_index] = list(row["references"])
            results[item_index] = [str(row["caption"])]
            index_rows[item_index] = (model, row)
            item_index += 1

    _average, detailed = Spice().compute_score(ground_truth, results)
    values_by_model: dict[str, list[float]] = defaultdict(list)
    sample_rows = []
    for index, score_set in enumerate(detailed):
        model, row = index_rows[index]
        value = float(score_set["All"]["f"])
        values_by_model[model].append(value)
        sample_rows.append(
            {"sample_id": row["sample_id"], "model": model, "SPICE": value}
        )
    summaries = {
        model: {"count": len(values), "SPICE": sum(values) / len(values)}
        for model, values in values_by_model.items()
    }
    return summaries, sample_rows


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(args.manifest)
    selected_by_model = {
        model: sorted(
            (row for row in rows if row["model"] == model),
            key=lambda row: row["sample_id"],
        )
        for model in args.models
    }
    for model, selected in selected_by_model.items():
        if len(selected) != 1000:
            raise ValueError(f"Expected 1000 rows for {model}, got {len(selected)}")

    summary = {
        "scope": "project-recomputed Draft/Refined on the aligned 1000-scene LEVIR-MCI subset",
        "models": {model: {"count": len(rows)} for model, rows in selected_by_model.items()},
        "configuration": {
            "BERTScore": {
                "model_type": args.bertscore_model,
                "num_layers": args.bertscore_layers,
                "idf": False,
                "rescale_with_baseline": False,
            },
            "SPICE": "pycocoevalcap 1.2 official Java implementation",
        },
    }
    samples: dict[tuple[str, str], dict] = {}
    if "bertscore" in args.metrics:
        metric_summary, metric_rows = run_bertscore(
            selected_by_model,
            model_type=args.bertscore_model,
            num_layers=args.bertscore_layers,
            batch_size=args.batch_size,
            device=args.device,
        )
        for model, values in metric_summary.items():
            summary["models"][model].update(values)
        for row in metric_rows:
            samples.setdefault((row["sample_id"], row["model"]), {}).update(row)
    if "spice" in args.metrics:
        metric_summary, metric_rows = run_spice(selected_by_model)
        for model, values in metric_summary.items():
            summary["models"][model].update(values)
        for row in metric_rows:
            samples.setdefault((row["sample_id"], row["model"]), {}).update(row)

    (args.output_dir / "semantic_metric_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(
        args.output_dir / "semantic_metric_samples.jsonl",
        sorted(samples.values(), key=lambda row: (row["sample_id"], row["model"])),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
