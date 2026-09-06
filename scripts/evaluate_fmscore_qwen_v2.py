"""Run the FMScore fact-deduction protocol with robust Qwen batch decoding."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from transformers import AutoModelForImageTextToText, AutoProcessor


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def facts(row: dict) -> list[str]:
    base = row["base_semantics"]; location = str(base["location"]).replace("-", " ")
    return [f"{base['source_entity']} areas disappeared in the {location}",
            f"{base['target_entity']} areas appeared in the {location}"]


def make_prompt(caption: str, fact: str) -> str:
    return ("Decide whether the paragraph explicitly states the fact. Ignore plausibility and answer "
            "with exactly one token: Yes or No.\nParagraph: " + caption + "\nFact: " + fact)


def parse(text: str) -> int | None:
    tokens = re.sub(r"[^a-z]+", " ", text.lower()).split()
    return 1 if "yes" in tokens else (0 if "no" in tokens else None)


def generate(processor, model, prompts: list[str]) -> list[str]:
    messages = [[{"role": "user", "content": [{"type": "text", "text": value}]}] for value in prompts]
    text = [processor.apply_chat_template(item, tokenize=False, add_generation_prompt=True) for item in messages]
    processor.tokenizer.padding_side = "left"
    inputs = processor(text=text, padding=True, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False, max_new_tokens=8)
    # Slice each sequence by the common padded input width, not unpadded lengths.
    generated = output[:, inputs["input_ids"].shape[1] :]
    return processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)


def best_bacc(labels: list[int], scores: list[float]) -> dict:
    ts = sorted(set(scores)); candidates = [ts[0] - 1e-9, *ts, ts[-1] + 1e-9]
    value, threshold = max((float(balanced_accuracy_score(labels, [int(x >= t) for x in scores])), float(t))
                           for t in candidates)
    return {"balanced_accuracy_oracle_threshold": value, "oracle_threshold": threshold}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path); parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-rows", type=int, default=0); args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True); rows = read_jsonl(args.manifest)
    if args.max_rows: rows = rows[:args.max_rows]
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(args.model, dtype=torch.bfloat16, device_map="auto"); model.eval()
    tasks = [(i, j, fact, make_prompt(str(row["caption"]), fact)) for i, row in enumerate(rows)
             for j, fact in enumerate(facts(row))]
    answers = {}; started = time.perf_counter()
    for start in range(0, len(tasks), args.batch_size):
        batch = tasks[start:start + args.batch_size]; generated = generate(processor, model, [x[3] for x in batch])
        for task, text in zip(batch, generated, strict=True):
            answers[(task[0], task[1])] = {"fact": task[2], "answer": " ".join(text.strip().split()), "binary": parse(text)}
        if start == 0 or (start + len(batch)) % 200 == 0 or start + len(batch) == len(tasks):
            print(f"questions {start + len(batch)}/{len(tasks)}", flush=True)
    outputs, labels, scores, grouped = [], [], [], defaultdict(list); failures = 0
    for i, row in enumerate(rows):
        item_answers = [answers[(i, j)] for j in range(2)]; failures += sum(x["binary"] is None for x in item_answers)
        binaries = [0 if x["binary"] is None else x["binary"] for x in item_answers]; value = float(np.mean(binaries))
        label, error = int(bool(row["is_factually_correct"])), str(row["error_type"])
        labels.append(label); scores.append(value); grouped[error].append(value)
        outputs.append({"item_id": row["item_id"], "sample_id": row["sample_id"], "error_type": error,
                        "is_factually_correct": bool(label), "caption": row["caption"], "facts": item_answers, "fmscore": value})
    (args.output_dir / "scores.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in outputs), encoding="utf-8")
    factual = float(np.mean([x for x, y in zip(scores, labels, strict=True) if y])); by_error = {}
    for error, values in sorted(grouped.items()):
        value = float(np.mean(values)); by_error[error] = {"count": len(values), "mean": value, "drop_from_factual": factual - value}
    summary = {"protocol": "FMScore yes/no fact-deduction protocol", "reasoner": args.model,
               "reasoner_note": "Local Qwen3-VL-2B deterministic protocol reproduction; original paper uses Vicuna-13B.",
               "manifest": str(args.manifest.resolve()), "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
               "rows": len(rows), "questions": len(tasks), "parse_failures": failures, "factual_mean": factual,
               "roc_auc": float(roc_auc_score(labels, scores)), **best_bacc(labels, scores), "by_error_type": by_error,
               "elapsed_seconds": time.perf_counter() - started}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
