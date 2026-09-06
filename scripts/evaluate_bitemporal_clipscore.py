"""Compute a transparent single-image CLIP aggregation baseline for change captions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=("Draft", "Refined"))
    parser.add_argument("--model", default="ViT-B-32")
    parser.add_argument("--pretrained", default="openai")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=64)
    return parser


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_rgb(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        args.model, pretrained=args.pretrained, device=args.device
    )
    tokenizer = open_clip.get_tokenizer(args.model)
    model.eval()
    selected = sorted(
        (row for row in read_jsonl(args.manifest) if row["model"] in args.models),
        key=lambda row: (row["model"], row["sample_id"]),
    )
    sample_rows = []
    with torch.inference_mode():
        for start in range(0, len(selected), args.batch_size):
            batch = selected[start : start + args.batch_size]
            pre_images = torch.stack(
                [preprocess(load_rgb(row["pre_image"])) for row in batch]
            ).to(args.device)
            post_images = torch.stack(
                [preprocess(load_rgb(row["post_image"])) for row in batch]
            ).to(args.device)
            texts = tokenizer([row["caption"] for row in batch]).to(args.device)
            pre_features = torch.nn.functional.normalize(model.encode_image(pre_images), dim=-1)
            post_features = torch.nn.functional.normalize(model.encode_image(post_images), dim=-1)
            text_features = torch.nn.functional.normalize(model.encode_text(texts), dim=-1)
            pre_similarity = (pre_features * text_features).sum(dim=-1).cpu().tolist()
            post_similarity = (post_features * text_features).sum(dim=-1).cpu().tolist()
            for index, row in enumerate(batch):
                pre_value = float(pre_similarity[index])
                post_value = float(post_similarity[index])
                sample_rows.append(
                    {
                        "sample_id": row["sample_id"],
                        "model": row["model"],
                        "CLIPScore-pre": pre_value,
                        "CLIPScore-post": post_value,
                        "BiTemporal-CLIP-mean": (pre_value + post_value) / 2.0,
                        "BiTemporal-CLIP-max": max(pre_value, post_value),
                    }
                )
            print(f"[{min(start + args.batch_size, len(selected))}/{len(selected)}]", flush=True)

    summary = {
        "protocol": "single-image-CLIP-aggregation-v1",
        "model": args.model,
        "pretrained": args.pretrained,
        "models": {},
        "interpretation": (
            "pre/post image-text cosine similarities are averaged; this is a transparent "
            "single-image aggregation baseline and does not explicitly encode temporal direction"
        ),
    }
    for model_name in args.models:
        rows = [row for row in sample_rows if row["model"] == model_name]
        summary["models"][model_name] = {
            "count": len(rows),
            "CLIPScore-pre": sum(row["CLIPScore-pre"] for row in rows) / len(rows),
            "CLIPScore-post": sum(row["CLIPScore-post"] for row in rows) / len(rows),
            "BiTemporal-CLIP-mean": (
                sum(row["BiTemporal-CLIP-mean"] for row in rows) / len(rows)
            ),
            "BiTemporal-CLIP-max": (
                sum(row["BiTemporal-CLIP-max"] for row in rows) / len(rows)
            ),
        }
    (args.output_dir / "clipscore_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(args.output_dir / "clipscore_samples.jsonl", sample_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
