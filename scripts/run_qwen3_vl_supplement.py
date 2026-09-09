"""Generate open-change QA answers and claim-preserving caption rewrites."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import defaultdict, deque
from pathlib import Path

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--hybrid-results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--qa-scenes", type=int, default=40)
    parser.add_argument("--rewrite-per-model", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--max-pixels", type=int, default=256 * 256)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def balanced_facts(rows: list[dict], limit: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        transition = row["transitions"][0]
        grouped[
            f"{transition['source_entity']}->{transition['target_entity']}"
        ].append(row)
    queues = {}
    for key, values in grouped.items():
        rng.shuffle(values)
        queues[key] = deque(values)
    selected = []
    keys = sorted(queues)
    while len(selected) < limit and keys:
        next_keys = []
        for key in keys:
            if queues[key] and len(selected) < limit:
                selected.append(queues[key].popleft())
            if queues[key]:
                next_keys.append(key)
        keys = next_keys
    return selected


def choose_rewrites(
    results: list[dict], manifest: list[dict], per_model: int, seed: int
) -> list[dict]:
    manifest_map = {
        (row["sample_id"], row["model"]): row for row in manifest
    }
    rng = random.Random(seed)
    selected = []
    for model_name in ("Draft", "Change-Agent"):
        candidates = [
            row
            for row in results
            if row.get("model") == model_name
            and row.get("claims")
            and any(
                claim.get("role") == "changed"
                for claim in row.get("claims", [])
            )
            and (row["sample_id"], row["model"]) in manifest_map
        ]
        rng.shuffle(candidates)
        for row in candidates[:per_model]:
            source = manifest_map[(row["sample_id"], row["model"])]
            selected.append(
                {
                    **row,
                    "reference_caption": source.get("metadata", {}).get(
                        "ground_truth_caption", ""
                    ),
                }
            )
    return selected


class QwenRunner:
    def __init__(self, model_path: str, max_pixels: int) -> None:
        self.processor = AutoProcessor.from_pretrained(
            model_path,
            max_pixels=max_pixels,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map="auto",
        )
        self.model.eval()

    @torch.inference_mode()
    def generate(
        self,
        *,
        prompt: str,
        images: tuple[str, ...] = (),
        max_new_tokens: int = 96,
    ) -> str:
        content = [
            {"type": "image", "image": str(Path(path).resolve())}
            for path in images
        ]
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)
        output = self.model.generate(
            **inputs,
            do_sample=False,
            max_new_tokens=max_new_tokens,
        )
        trimmed = output[:, inputs["input_ids"].shape[-1] :]
        text = self.processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return " ".join(text.strip().split())


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    facts = balanced_facts(read_jsonl(args.facts), args.qa_scenes, args.seed)
    rewrite_inputs = choose_rewrites(
        read_jsonl(args.hybrid_results),
        read_jsonl(args.manifest),
        args.rewrite_per_model,
        args.seed,
    )
    runner = QwenRunner(args.model, args.max_pixels)
    qa_rows = []
    rewrite_rows = []
    started = time.perf_counter()

    qa_prompt = (
        "The first overhead image is before the change and the second is after. "
        "What is the single dominant land-cover transition in the changed region? "
        "Answer with one concise factual sentence that explicitly names the old "
        "land-cover type, the new land-cover type, and the approximate location. "
        "Do not use placeholder words, do not name unchanged objects, and do not "
        "provide explanations."
    )
    for index, fact in enumerate(facts, start=1):
        answer = runner.generate(
            prompt=qa_prompt,
            images=(fact["pre_image"], fact["post_image"]),
        )
        qa_rows.append(
            {
                "sample_id": fact["sample_id"],
                "question": qa_prompt,
                "answer": answer,
                "pre_image": fact["pre_image"],
                "post_image": fact["post_image"],
                "pre_label": fact["pre_label"],
                "post_label": fact["post_label"],
                "expected_transition": fact["transitions"][0],
                "model": args.model,
            }
        )
        print(f"qa {index}/{len(facts)}", flush=True)

    rewrite_prompt = (
        "Rewrite the remote-sensing change caption below into a more natural and "
        "semantically rich single sentence. Preserve every factual claim exactly: "
        "do not add or remove entities, change add/remove/no-change direction, "
        "location, count, or attributes. Output only the rewritten sentence.\n\n"
        "Caption: {caption}"
    )
    for index, row in enumerate(rewrite_inputs, start=1):
        rewritten = runner.generate(
            prompt=rewrite_prompt.format(caption=row["caption"]),
            max_new_tokens=96,
        )
        rewrite_rows.append(
            {
                "sample_id": row["sample_id"],
                "model": row["model"],
                "original_caption": row["caption"],
                "rewritten_caption": rewritten,
                "reference_caption": row["reference_caption"],
                "original_claims": row["claims"],
                "original_score": row["score"],
                "generator": args.model,
            }
        )
        print(f"rewrite {index}/{len(rewrite_inputs)}", flush=True)

    write_jsonl(args.output_dir / "qa_outputs.jsonl", qa_rows)
    write_jsonl(args.output_dir / "rewrite_outputs.jsonl", rewrite_rows)
    manifest = {
        "model": args.model,
        "qa_scene_count": len(qa_rows),
        "rewrite_count": len(rewrite_rows),
        "rewrite_models": ["Draft", "Change-Agent"],
        "seed": args.seed,
        "runtime_seconds": time.perf_counter() - started,
        "qa_outputs": str(args.output_dir / "qa_outputs.jsonl"),
        "rewrite_outputs": str(args.output_dir / "rewrite_outputs.jsonl"),
    }
    (args.output_dir / "generation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
