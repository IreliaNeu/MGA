"""Create Markdown, CSV, and contact-sheet summaries for a SegEarth MGA batch."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_contact_sheet(run_dir: Path) -> Path | None:
    image_paths = sorted((run_dir / "scenes").glob("*/overview_A_B_reference.png"))
    if not image_paths:
        return None

    columns = min(2, len(image_paths))
    card_width = 768
    label_height = 28
    image_height = 284
    rows = math.ceil(len(image_paths) / columns)
    sheet = Image.new(
        "RGB", (columns * card_width, rows * (label_height + image_height)), "white"
    )
    draw = ImageDraw.Draw(sheet)
    for index, image_path in enumerate(image_paths):
        column = index % columns
        row = index // columns
        x = column * card_width
        y = row * (label_height + image_height)
        draw.rectangle((x, y, x + card_width, y + label_height), fill=(25, 25, 25))
        draw.text((x + 8, y + 7), image_path.parent.name, fill="white")
        with Image.open(image_path) as source:
            panel = source.convert("RGB")
            panel.thumbnail((card_width, image_height), Image.Resampling.LANCZOS)
            sheet.paste(panel, (x, y + label_height))

    output = run_dir / "batch_overview_contact_sheet.png"
    sheet.save(output, optimize=True)
    return output


def main() -> int:
    args = build_parser().parse_args()
    summary = json.loads((args.run_dir / "summary.json").read_text(encoding="utf-8"))
    scores = _jsonl(args.run_dir / "mga_scores.jsonl")
    segmentations = _jsonl(args.run_dir / "segmentations.jsonl")

    caption_rows = []
    claim_rows = []
    entity_scenes: dict[str, set[str]] = defaultdict(set)
    change_types: Counter[str] = Counter()
    for row in scores:
        score = row["score"]
        caption_rows.append(
            {
                "sample_id": row["sample_id"],
                "model": row["model"],
                "faithfulness": score["faithfulness"],
                "coverage": score["coverage"],
                "temporal": score["temporal"],
                "overall": score["overall"],
                "unverifiable_rate": score["unverifiable_rate"],
                "caption": row["caption"],
                "visualization": row["visualization"],
            }
        )
        claims = {claim["claim_id"]: claim for claim in row["claims"]}
        for claim_score in score["claim_scores"]:
            claim = claims[claim_score["claim_id"]]
            entity = claim["entity"]
            entity_scenes[entity].add(row["sample_id"])
            change_types[claim["change_type"]] += 1
            claim_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "model": row["model"],
                    "claim_id": claim["claim_id"],
                    "entity": entity,
                    "change_type": claim["change_type"],
                    "role": claim["role"],
                    "status": claim_score["status"],
                    "faithfulness": claim_score["faithfulness"],
                    "spatial_support": claim_score["spatial_support"],
                    "temporal_support": claim_score["temporal_support"],
                    "grounding_confidence": claim_score["grounding_confidence"],
                    "reason": claim_score["reason"],
                }
            )

    segmentation_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prompt_presence: dict[tuple[str, str], list[float]] = defaultdict(list)
    prompt_wins: Counter[tuple[str, str]] = Counter()
    for scene in segmentations:
        for phase in ("A", "B"):
            for item in scene[phase]:
                entity = item["entity"]
                segmentation_stats[entity].append(item)
                pairs = list(zip(item["queries"], item["presence_scores"], strict=False))
                for prompt, presence in pairs:
                    prompt_presence[(entity, prompt)].append(float(presence))
                if pairs:
                    winning_prompt, _score = max(pairs, key=lambda pair: pair[1])
                    prompt_wins[(entity, winning_prompt)] += 1

    scene_models: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in caption_rows:
        scene_models[row["sample_id"]][row["model"]] = row

    lines = [
        "# SegEarth-OV-3 小批量 MGA 流程报告",
        "",
        f"- 场景数：{summary['scenes']}",
        f"- Caption 数：{summary['captions']}",
        f"- 总耗时：{summary['elapsed_seconds']:.2f} 秒",
        f"- 峰值显存：{summary['peak_gpu_memory_mib']:.1f} MiB",
        f"- 后端：`{summary['backend']}`",
        "- 整批联合可视化：[batch_overview_contact_sheet.png](batch_overview_contact_sheet.png)",
        "",
        "## 分模型 MGA v2 均值",
        "",
        "| 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, values in summary["by_model"].items():
        lines.append(
            f"| {model} | {_fmt(values['faithfulness'])} | {_fmt(values['coverage'])} | "
            f"{_fmt(values['temporal'])} | {_fmt(values['overall'])} | "
            f"{_fmt(values['unverifiable_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## 分实体诊断",
            "",
            "| 实体 | Claims | Faithfulness | Spatial | Temporal | Confidence | 状态 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for entity, values in summary["by_entity"].items():
        status_text = ", ".join(
            f"{name}={count}" for name, count in sorted(values["statuses"].items())
        )
        lines.append(
            f"| {entity} | {values['claims']} | {_fmt(values['faithfulness'])} | "
            f"{_fmt(values['spatial_support'])} | {_fmt(values['temporal_support'])} | "
            f"{_fmt(values['grounding_confidence'])} | {status_text} |"
        )

    lines.extend(
        [
            "",
            "## 场景 × 模型 Overall",
            "",
            "| 场景 | Draft | Guided | Change-Agent |",
            "|---|---:|---:|---:|",
        ]
    )
    for sample_id, models in scene_models.items():
        lines.append(
            f"| {sample_id} | {_fmt(models.get('Draft', {}).get('overall'))} | "
            f"{_fmt(models.get('Guided', {}).get('overall'))} | "
            f"{_fmt(models.get('Change-Agent', {}).get('overall'))} |"
        )

    lines.extend(
        [
            "",
            "## 分割掩膜健康度",
            "",
            "| 实体 | 图像数 | 平均面积占比 | 空掩膜 | 近整图掩膜 | 平均置信度 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for entity, rows in sorted(segmentation_stats.items()):
        fractions = [float(row["mask_fraction"]) for row in rows]
        confidences = [float(row["confidence"]) for row in rows]
        lines.append(
            f"| {entity} | {len(rows)} | {sum(fractions) / len(fractions):.3f} | "
            f"{sum(value < 0.001 for value in fractions)} | "
            f"{sum(value > 0.95 for value in fractions)} | "
            f"{sum(confidences) / len(confidences):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Claim 解析覆盖",
            "",
            f"- Change type 分布：{dict(change_types)}",
            "- 出现 building claim 的场景："
            f"{len(entity_scenes.get('building', set()))}/{summary['scenes']}",
            "- 出现 house claim 的场景："
            f"{len(entity_scenes.get('house', set()))}/{summary['scenes']}",
            "- 出现 road claim 的场景："
            f"{len(entity_scenes.get('road', set()))}/{summary['scenes']}",
            "",
            "## 同义词 Presence 胜出次数",
            "",
            "| 实体 | Prompt | 胜出次数 | 平均 Presence |",
            "|---|---|---:|---:|",
        ]
    )
    for (entity, prompt), wins in sorted(
        prompt_wins.items(), key=lambda item: (item[0][0], -item[1], item[0][1])
    ):
        values = prompt_presence[(entity, prompt)]
        lines.append(f"| {entity} | {prompt} | {wins} | {sum(values) / len(values):.3f} |")

    lines.extend(
        [
            "",
            "## 最低 Faithfulness Claims",
            "",
            "| 场景 | 模型 | 实体 | 状态 | Faithfulness | Spatial | Temporal | Confidence |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    ranked_claims = sorted(
        (row for row in claim_rows if row["faithfulness"] is not None),
        key=lambda row: row["faithfulness"],
    )[:15]
    for row in ranked_claims:
        lines.append(
            f"| {row['sample_id']} | {row['model']} | {row['entity']} | {row['status']} | "
            f"{_fmt(row['faithfulness'])} | {_fmt(row['spatial_support'])} | "
            f"{_fmt(row['temporal_support'])} | {_fmt(row['grounding_confidence'])} |"
        )

    contact_sheet = _write_contact_sheet(args.run_dir)
    (args.run_dir / "report.zh-CN.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    _write_csv(args.run_dir / "caption_scores.csv", caption_rows)
    _write_csv(args.run_dir / "claim_scores.csv", claim_rows)
    print(f"Wrote report and CSV files to {args.run_dir}")
    if contact_sheet is not None:
        print(f"Wrote contact sheet to {contact_sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
