"""Generate two deliberately different, claim-preserving rewrite styles."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from run_qwen3_vl_supplement import QwenRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--per-model", type=int, default=10)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    args = parse_args()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in read_jsonl(args.inputs):
        grouped[str(row["model"])].append(row)
    selected = [
        row
        for model in ("Draft", "Change-Agent")
        for row in grouped[model][: args.per_model]
    ]
    runner = QwenRunner(args.model, max_pixels=256 * 256)
    prompts = {
        "technical_nominalized": (
            "Express the following remote-sensing change caption as a compact "
            "technical observation using a substantially different sentence "
            "structure and lexical wording. Preserve every entity, change "
            "direction, location, count, and attribute exactly. Do not add "
            "explanations or new facts. Output one sentence only. Avoid copying "
            "any sequence of more than two consecutive content words.\n\n"
            "Caption: {caption}"
        ),
        "active_narrative": (
            "Paraphrase the following remote-sensing change caption in an active, "
            "natural narrative style with different syntax and synonyms. Preserve "
            "every entity, change direction, location, count, and attribute "
            "exactly. Do not add explanations or new facts. Output one sentence "
            "only. Avoid copying any sequence of more than two consecutive "
            "content words.\n\nCaption: {caption}"
        ),
    }
    output_rows = []
    total = len(selected) * len(prompts)
    index = 0
    for row in selected:
        for style, prompt in prompts.items():
            index += 1
            rewritten = runner.generate(
                prompt=prompt.format(caption=row["original_caption"]),
                max_new_tokens=96,
            )
            output_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "model": f"{row['model']}:{style}",
                    "source_model": row["model"],
                    "style": style,
                    "original_caption": row["original_caption"],
                    "rewritten_caption": rewritten,
                    "reference_caption": row["reference_caption"],
                    "original_claims": row["original_claims"],
                    "original_score": row["original_score"],
                    "generator": args.model,
                }
            )
            print(f"style rewrite {index}/{total}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
