"""Evaluate the published FMScore protocol with a local Qwen3-VL reasoner.

FMScore asks an LLM whether each ground-truth fact is referenced by a generated
change paragraph and averages binary yes/no answers.  This implementation uses
the same question structure with deterministic decoding.  It is a protocol
reproduction with Qwen3-VL-2B, not a claim of reproducing the paper's Vicuna-13B
numbers.
"""

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


def fact_sentences(row: dict) -> list[str]:
    base = row["base_semantics"]
    location = str(base["location"]).replace("-", " ")
    return [
        f"{base['source_entity']} areas disappeared in the {location}",
        f"{base['target_entity']} areas appeared in the {location}",
    ]


def prompt(caption: str, fact: str) -> str:
    return (
        "Here is a paragraph describing some changes: " + caption + "\n"
        "In the paragraph, are there references to the fact that " + fact + "?\n"
        "Answer only Yes or No."
    )


def parse_yes_no(text: str) -> int | None:
    normalized = re.sub(r"[^a-z]+", " ", text.lower()).strip().split()
    for token in normalized:
        if token == "yes":
            return 1
        if token == "no":
            return 0
    return None


def generate_batch(processor, model, prompts: list[str]) -> list[str]:
    conversations = [[{"role": "user", "content": [{"type": "text", "text": value}]}] for value in prompts]
    texts = [
        processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        for messages in conversations
    ]
    inputs = processor(text=texts, padding=True, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False, max_new_tokens=16)
    input_length = inputs["input_ids"].shape[1]
    return processor.batch_decode(output[:, input_length:], skip_special_tokens=True,
                                  clean_up_tokenization_spaces=False)


def best_bacc(labels: list[int], scores: list[float]) -> dict:
    thresholds = sorted(set(scores))
    candidates = [thresholds[0] - 1e-9, *thresholds, thresholds[-1] + 1e-9]
    value, threshold = max(
        (float(balanced_accuracy_score(labels, [int(score >= t) for score in scores])), float(t))
        for t in candidates
    )
    return {"balanced_accuracy_oracle_threshold": value, "oracle_threshold": threshold}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(args.manifest)
    if args.max_rows:
        rows = rows[: args.max_rows]
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="auto")
    model.eval()
    tasks = []
    for row_index, row in enumerate(rows):
        for fact_index, fact in enumerate(fact_sentences(row)):
            tasks.append((row_index, fact_index, fact, prompt(str(row["caption"]), fact)))
    raw_answers: dict[tuple[int, int], dict] = {}
    started = time.perf_counter()
    for start in range(0, len(tasks), args.batch_size):
        batch = tasks[start : start + args.batch_size]
        answers = generate_batch(processor, model, [task[3] for task in batch])
        for task, answer in zip(batch, answers, strict=True):
            raw_answers[(task[0], task[1])] = {
                "fact": task[2], "answer": " ".join(answer.strip().split()),
                "binary": parse_yes_no(answer),
            }
        print(f"questions {min(start + len(batch), len(tasks))}/{len(tasks)}", flush=True)
    outputs, labels, scores, grouped = [], [], [], defaultdict(list)
    parse_failures = 0
    for index, row in enumerate(rows):
        answers = [raw_answers[(index, fact_index)] for fact_index in range(2)]
        parse_failures += sum(answer["binary"] is None for answer in answers)
        binary = [0 if answer["binary"] is None else int(answer["binary"]) for answer in answers]
        fmscore = float(np.mean(binary))
        label, error = int(bool(row["is_factually_correct"])), str(row["error_type"])
        labels.append(label); scores.append(fmscore); grouped[error].append(fmscore)
        outputs.append({"item_id": row["item_id"], "sample_id": row["sample_id"],
                        "error_type": error, "is_factually_correct": bool(label),
                        "caption": row["caption"], "facts": answers, "fmscore": fmscore})
    output_path = args.output_dir / "scores.jsonl"
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
    factual = float(np.mean([score for score, label in zip(scores, labels, strict=True) if label]))
    by_error = {}
    for error, values in sorted(grouped.items()):
        value = float(np.mean(values))
        by_error[error] = {"count": len(values), "mean": value, "drop_from_factual": factual - value}
    summary = {
        "protocol": "FMScore yes/no fact-deduction protocol",
        "reasoner": args.model,
        "reasoner_note": "Local Qwen3-VL-2B deterministic protocol reproduction; original paper uses Vicuna-13B.",
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "rows": len(rows), "questions": len(tasks), "parse_failures": parse_failures,
        "factual_mean": factual, "roc_auc": float(roc_auc_score(labels, scores)),
        **best_bacc(labels, scores), "by_error_type": by_error,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
