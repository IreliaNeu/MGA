"""Organize uploaded AutoDL archives into an MGA-ready aligned dataset.

The source archives are treated as immutable. Only the 1,000 LEVIR-MCI test
samples referenced by the feedback JSONL are extracted. WHU-CD Change-Agent
texts are kept in a separate directory because no aligned WHU images are part
of the current upload.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PIL import Image

MASK_CLASSES = {0: "background", 1: "road", 2: "building"}
SOURCE_MASK_VALUES = {0: 0, 128: 1, 255: 2}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Align LEVIR-MCI images, feedback JSONL, and Change-Agent text outputs"
    )
    parser.add_argument("--dataset-zip", required=True, type=Path)
    parser.add_argument("--feedback-jsonl", required=True, type=Path)
    parser.add_argument("--change-agent-zip", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def _index_dataset(zip_file: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    channels = {"A", "B", "label", "label_rgb"}
    index: dict[str, dict[str, str]] = {channel: {} for channel in channels}
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        parts = PurePosixPath(info.filename).parts
        if len(parts) < 3 or parts[-3] != "test" or parts[-2] not in channels:
            continue
        channel = parts[-2]
        stem = PurePosixPath(parts[-1]).stem
        if stem in index[channel]:
            raise ValueError(f"Duplicate {channel} archive member for {stem}")
        index[channel][stem] = info.filename
    return index


def _index_change_agent(zip_file: zipfile.ZipFile) -> dict[str, str]:
    index: dict[str, str] = {}
    for info in zip_file.infolist():
        if info.is_dir() or PurePosixPath(info.filename).suffix.lower() != ".txt":
            continue
        stem = PurePosixPath(info.filename).stem
        if stem in index:
            raise ValueError(f"Duplicate Change-Agent archive member for {stem}")
        index[stem] = info.filename
    return index


def _copy_member(zip_file: zipfile.ZipFile, member: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zip_file.open(member) as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target)


def _write_class_mask(zip_file: zipfile.ZipFile, member: str, destination: Path) -> None:
    with Image.open(BytesIO(zip_file.read(member))) as source:
        raw = np.asarray(source.convert("RGB"))
    if not np.array_equal(raw[..., 0], raw[..., 1]) or not np.array_equal(
        raw[..., 1], raw[..., 2]
    ):
        raise ValueError(f"Expected grayscale RGB source label: {member}")
    values = set(int(value) for value in np.unique(raw[..., 0]))
    unexpected = values - SOURCE_MASK_VALUES.keys()
    if unexpected:
        raise ValueError(f"Unexpected label values in {member}: {sorted(unexpected)}")
    class_ids = np.zeros(raw.shape[:2], dtype=np.uint8)
    for source_value, class_id in SOURCE_MASK_VALUES.items():
        class_ids[raw[..., 0] == source_value] = class_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(class_ids).save(destination)


def _required_text(row: dict[str, Any], key: str, sample_id: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Feedback row {sample_id} has no {key!r}")
    return value


def organize(
    dataset_zip: Path,
    feedback_jsonl: Path,
    change_agent_zip: Path,
    output_root: Path,
) -> dict[str, Any]:
    for source in (dataset_zip, feedback_jsonl, change_agent_zip):
        if not source.is_file():
            raise FileNotFoundError(source)
    if output_root.exists():
        raise FileExistsError(f"Output already exists; refusing to overwrite: {output_root}")

    staging = output_root.with_name(output_root.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"Staging directory already exists: {staging}")
    staging.mkdir(parents=True)

    feedback_rows = read_jsonl(feedback_jsonl)
    if not feedback_rows:
        raise ValueError("Feedback JSONL is empty")

    mapping_rows: list[dict[str, Any]] = []
    aligned_feedback_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_stems: set[str] = set()

    with zipfile.ZipFile(dataset_zip) as dataset, zipfile.ZipFile(
        change_agent_zip
    ) as change_agent:
        dataset_index = _index_dataset(dataset)
        change_index = _index_change_agent(change_agent)

        for line_number, source_row in enumerate(feedback_rows, start=1):
            sample_id = str(source_row.get("id") or source_row.get("sample_id") or "")
            source_image = str(source_row.get("image_A_path") or "")
            stem = Path(source_image).stem
            if not sample_id or not stem:
                raise ValueError(f"Missing id/image_A_path at feedback line {line_number}")
            if sample_id in seen_ids or stem in seen_stems:
                raise ValueError(f"Duplicate sample id or image stem: {sample_id}/{stem}")
            seen_ids.add(sample_id)
            seen_stems.add(stem)

            members = {channel: dataset_index[channel].get(stem) for channel in dataset_index}
            missing_channels = [channel for channel, member in members.items() if member is None]
            if missing_channels:
                raise ValueError(f"{sample_id} is missing dataset members: {missing_channels}")
            change_member = change_index.get(stem)
            if change_member is None:
                raise ValueError(f"{sample_id} is missing Change-Agent output {stem}.txt")

            final_pre = output_root / "images" / "A" / f"{stem}.png"
            final_post = output_root / "images" / "B" / f"{stem}.png"
            final_source_label = output_root / "masks" / "source_label" / f"{stem}.png"
            final_source_rgb = output_root / "masks" / "source_label_rgb" / f"{stem}.png"
            final_class_mask = output_root / "masks" / "class_id" / f"{stem}.png"
            final_change_text = output_root / "results" / "change_agent" / "levir" / f"{stem}.txt"

            _copy_member(dataset, str(members["A"]), staging / final_pre.relative_to(output_root))
            _copy_member(dataset, str(members["B"]), staging / final_post.relative_to(output_root))
            _copy_member(
                dataset,
                str(members["label"]),
                staging / final_source_label.relative_to(output_root),
            )
            _copy_member(
                dataset,
                str(members["label_rgb"]),
                staging / final_source_rgb.relative_to(output_root),
            )
            _write_class_mask(
                dataset,
                str(members["label"]),
                staging / final_class_mask.relative_to(output_root),
            )
            _copy_member(
                change_agent,
                change_member,
                staging / final_change_text.relative_to(output_root),
            )
            change_caption = change_agent.read(change_member).decode("utf-8").strip()
            if not change_caption:
                raise ValueError(f"Empty Change-Agent caption: {change_member}")

            mapping_rows.append(
                {
                    "sample_id": sample_id,
                    "image_stem": stem,
                    "pre_image": str(final_pre),
                    "post_image": str(final_post),
                    "change_mask": str(final_class_mask),
                    "source_label": str(final_source_label),
                    "source_label_rgb": str(final_source_rgb),
                    "change_agent_file": str(final_change_text),
                    "source_archive_members": {
                        **members,
                        "change_agent": change_member,
                    },
                }
            )

            aligned_feedback = {
                **source_row,
                "sample_id": sample_id,
                "image_A_path": str(final_pre),
                "image_B_path": str(final_post),
                "change_mask_path": str(final_class_mask),
                "source_image_stem": stem,
            }
            aligned_feedback_rows.append(aligned_feedback)

            common = {
                "sample_id": sample_id,
                "pre_image": str(final_pre),
                "post_image": str(final_post),
                "change_mask": str(final_class_mask),
                "dataset": "LEVIR-MCI",
                "split": "test",
                "feedback": source_row.get("feedback"),
                "metadata": {
                    "ground_truth_caption": source_row.get("gt"),
                    "feedback_status": source_row.get("status"),
                    "llm_judge_winner": source_row.get("Win_caption"),
                    "llm_judge_reason": source_row.get("reason_draft"),
                    "source_image_stem": stem,
                    "mask_class_map": {str(k): value for k, value in MASK_CLASSES.items()},
                    "source_feedback_jsonl": str(feedback_jsonl),
                },
            }
            manifest_rows.extend(
                [
                    {
                        **common,
                        "model": "Draft",
                        "caption": _required_text(source_row, "draft", sample_id),
                    },
                    {
                        **common,
                        "model": "Guided",
                        "caption": _required_text(source_row, "refined", sample_id),
                    },
                    {
                        **common,
                        "model": "Change-Agent",
                        "caption": change_caption,
                        "metadata": {
                            **common["metadata"],
                            "change_agent_file": str(final_change_text),
                        },
                    },
                ]
            )

        levir_change_stems = {stem for stem in change_index if stem.startswith("test_")}
        if levir_change_stems != seen_stems:
            raise ValueError(
                "LEVIR Change-Agent set does not match feedback set: "
                f"missing={len(seen_stems - levir_change_stems)}, "
                f"extra={len(levir_change_stems - seen_stems)}"
            )

        whu_rows: list[dict[str, Any]] = []
        whu_members = sorted(
            (stem, member) for stem, member in change_index.items() if stem.startswith("whucd_")
        )
        for stem, member in whu_members:
            final_path = output_root / "results" / "change_agent" / "whu" / f"{stem}.txt"
            _copy_member(change_agent, member, staging / final_path.relative_to(output_root))
            whu_rows.append(
                {
                    "sample_id": stem,
                    "dataset": "WHU-CD",
                    "caption": change_agent.read(member).decode("utf-8").strip(),
                    "change_agent_file": str(final_path),
                    "image_mapping_status": "unavailable_in_current_upload",
                }
            )

    manifests = staging / "manifests"
    write_jsonl(manifests / "path_mapping.jsonl", mapping_rows)
    write_jsonl(manifests / "feedback_aligned.jsonl", aligned_feedback_rows)
    write_jsonl(manifests / "all_models_manifest.jsonl", manifest_rows)
    write_jsonl(manifests / "whu_change_agent_index.jsonl", whu_rows)

    report = {
        "status": "aligned",
        "source_files": {
            "dataset_zip": str(dataset_zip),
            "feedback_jsonl": str(feedback_jsonl),
            "change_agent_zip": str(change_agent_zip),
        },
        "counts": {
            "feedback_samples": len(feedback_rows),
            "mapped_levir_samples": len(mapping_rows),
            "canonical_manifest_rows": len(manifest_rows),
            "levir_change_agent_texts": len(mapping_rows),
            "whu_change_agent_texts_without_images": len(whu_rows),
        },
        "mask_encoding": {
            "source_label_values": {"0": 0, "128": 1, "255": 2},
            "class_ids": {str(key): value for key, value in MASK_CLASSES.items()},
        },
        "output_root": str(output_root),
    }
    (staging / "reports").mkdir(parents=True, exist_ok=True)
    (staging / "reports" / "alignment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (staging / "README.md").write_text(
        "# Organized MGA data\n\n"
        "This directory was generated without modifying the uploaded archives.\n"
        "Use `manifests/all_models_manifest.jsonl` for Draft, Guided, and "
        "Change-Agent alignment. It has no atomic claims yet; run `mga parse` "
        "before scoring. `masks/class_id` uses 0=background, 1=road, "
        "2=building. WHU-CD texts are indexed separately because aligned images "
        "were not included in the current upload.\n",
        encoding="utf-8",
    )

    staging.rename(output_root)
    return report


def main() -> int:
    args = build_parser().parse_args()
    report = organize(
        args.dataset_zip,
        args.feedback_jsonl,
        args.change_agent_zip,
        args.output_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
