"""Adapters from existing experiment outputs to the canonical MGA manifest."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mga.io import read_jsonl, write_jsonl


def convert_feedback_jsonl(
    source: str | Path,
    output: str | Path,
    mask_root: str | Path,
    mask_template: str = "{image_stem}.png",
    dataset: str = "LEVIR-MCI",
) -> int:
    """Expand each feedback row into aligned Draft and Guided manifest rows."""
    mask_root = Path(mask_root)
    rows: list[dict[str, Any]] = []
    for item in read_jsonl(source):
        source_id = str(item.get("id") or item.get("sample_id") or "")
        image_a = str(item.get("image_A_path") or item.get("pre_image") or "")
        image_b = str(item.get("image_B_path") or item.get("post_image") or "")
        if not source_id or not image_a or not image_b:
            raise ValueError(f"Feedback row is missing id/image paths: {item}")
        image_stem = Path(image_a).stem
        mask_name = mask_template.format(
            id=source_id,
            sample_id=source_id,
            image_stem=image_stem,
        )
        common = {
            "sample_id": source_id,
            "pre_image": image_a,
            "post_image": image_b,
            "change_mask": str(mask_root / mask_name),
            "dataset": dataset,
            "split": "test",
            "feedback": item.get("feedback"),
            "metadata": {
                "ground_truth_caption": item.get("gt"),
                "feedback_status": item.get("status"),
                "llm_judge_winner": item.get("Win_caption"),
                "llm_judge_reason": item.get("reason_draft"),
                "llm_judge_model": item.get("judge_model"),
                "source_image_stem": image_stem,
                "source_format": "feedback_jsonl_v1",
            },
        }
        for model, key in (("Draft", "draft"), ("Guided", "refined")):
            caption = item.get(key)
            if not caption:
                raise ValueError(f"Feedback row {source_id} has no {key!r} caption")
            rows.append({**common, "model": model, "caption": str(caption)})
    write_jsonl(output, rows)
    return len(rows)


def attach_change_agent_texts(
    manifest_rows: Iterable[dict[str, Any]],
    results_dir: str | Path,
    output: str | Path,
    glob_pattern: str = "*.txt",
    model_name: str = "Change-Agent",
    strict: bool = True,
) -> tuple[int, list[str]]:
    """Append one Change-Agent caption per unique image pair.

    Text filenames may use either the canonical sample ID or the source image stem
    (for example ``test_000001.txt``). Existing manifest rows are preserved.
    """
    rows = list(manifest_rows)
    result_files = {path.stem: path for path in Path(results_dir).glob(glob_pattern)}
    unique_samples: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique_samples.setdefault(str(row["sample_id"]), row)

    missing: list[str] = []
    appended = 0
    for sample_id, source_row in unique_samples.items():
        metadata = dict(source_row.get("metadata", {}))
        candidates = (
            sample_id,
            str(metadata.get("source_image_stem", "")),
            Path(str(source_row.get("pre_image", ""))).stem,
        )
        result_path = next((result_files[key] for key in candidates if key in result_files), None)
        if result_path is None:
            missing.append(sample_id)
            continue
        caption = result_path.read_text(encoding="utf-8").strip()
        if not caption:
            missing.append(sample_id)
            continue
        rows.append(
            {
                "sample_id": sample_id,
                "model": model_name,
                "caption": caption,
                "pre_image": source_row["pre_image"],
                "post_image": source_row["post_image"],
                "change_mask": source_row["change_mask"],
                "dataset": source_row.get("dataset", "unknown"),
                "split": source_row.get("split", "test"),
                "metadata": {
                    **metadata,
                    "change_agent_file": str(result_path),
                    "source_format": "change_agent_text_v1",
                },
            }
        )
        appended += 1

    if strict and missing:
        preview = ", ".join(missing[:10])
        raise ValueError(f"Missing Change-Agent text for {len(missing)} samples: {preview}")
    write_jsonl(output, rows)
    return appended, missing
