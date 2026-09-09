"""Compare MGA v2 evidence constructions on one cached SegEarth batch."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from mga.io import load_manifest, read_jsonl, write_jsonl
from mga.mask_ops import load_label_mask
from mga.models import ClaimRole, EvidenceMode, GroundingEvidence, SampleRecord
from mga.scoring import MGAV2Config, MGAV2Scorer

METRICS = (
    "faithfulness",
    "coverage",
    "temporal",
    "overall",
    "unverifiable_rate",
)
MODE_DESCRIPTIONS = {
    EvidenceMode.FULL_TARGET: (
        "当前实现：Add 使用 post，Remove 使用 pre，Modify 使用 pre ∪ post。"
    ),
    EvidenceMode.TEMPORAL_DELTA: (
        "Add = post - pre，Remove = pre - post，Modify = pre XOR post。"
    ),
    EvidenceMode.GT_ROI_GATED: (
        "先用对应类别的真实变化 ROI 门控 pre/post，再判断时相存在性；这是乐观的 "
        "v1 风格对照。"
    ),
    EvidenceMode.MASK_LABEL_ONLY: (
        "不使用 SegEarth；Parser 的 target_labels 直接匹配真实标签 "
        "road=1、building=2，不能判断时相方向和静态上下文。"
    ),
    EvidenceMode.HYBRID_MASK_TEMPORAL: (
        "Spatial/Coverage 使用 Parser 直接匹配真实类别标签；Temporal 仅使用 "
        "SegEarth 的双时相证据。"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--segmentation-run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-scenes", type=int)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=[mode.value for mode in EvidenceMode],
        default=[mode.value for mode in EvidenceMode],
    )
    return parser


def _mean(values: list[float | None]) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    return float(sum(concrete) / len(concrete)) if concrete else None


def _mask(path: str, cache: dict[str, np.ndarray]) -> np.ndarray:
    if path not in cache:
        cache[path] = np.asarray(load_label_mask(path), dtype=bool)
    return cache[path]


def _segmentation_index(run_dir: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    rows = list(read_jsonl(run_dir / "segmentations.jsonl"))
    scene_order = [str(row["sample_id"]) for row in rows]
    return scene_order, {str(row["sample_id"]): row for row in rows}


def _phase_index(scene: dict[str, Any], phase: str) -> dict[str, dict[str, Any]]:
    return {
        str(item["entity"]).strip().lower(): item
        for item in scene.get(phase, [])
    }


def _evidence_for_record(
    record: SampleRecord,
    scene: dict[str, Any],
    mask_cache: dict[str, np.ndarray],
) -> dict[str, GroundingEvidence]:
    pre_items = _phase_index(scene, "A")
    post_items = _phase_index(scene, "B")
    result: dict[str, GroundingEvidence] = {}
    for claim in record.claims:
        entity = claim.entity.strip().lower()
        if claim.role == ClaimRole.NO_CHANGE or entity == "scene":
            result[claim.claim_id] = GroundingEvidence(backend="cached-segearth-ov3")
            continue
        pre_item = pre_items.get(entity)
        post_item = post_items.get(entity)
        if pre_item is None or post_item is None:
            result[claim.claim_id] = GroundingEvidence(
                backend="cached-segearth-ov3",
                metadata={"entity": entity, "missing_cached_entity": True},
            )
            continue
        result[claim.claim_id] = GroundingEvidence(
            pre_mask=_mask(str(pre_item["mask_path"]), mask_cache),
            post_mask=_mask(str(post_item["mask_path"]), mask_cache),
            pre_confidence=float(pre_item.get("confidence", 0.0)),
            post_confidence=float(post_item.get("confidence", 0.0)),
            backend="cached-segearth-ov3",
            metadata={"entity": entity, "reused_cached_masks": True},
        )
    return result


def _summarize_mode(rows: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    for row in rows:
        score = row["score"]
        by_model[row["model"]].append(score)
        claims = {claim["claim_id"]: claim for claim in row["claims"]}
        for claim_score in score["claim_scores"]:
            claim = claims[claim_score["claim_id"]]
            by_entity[claim["entity"]].append(claim_score)
            statuses[claim_score["status"]] += 1

    model_summary = {
        model: {
            "captions": len(scores),
            **{
                metric: _mean([score.get(metric) for score in scores])
                for metric in METRICS
            },
        }
        for model, scores in sorted(by_model.items())
    }
    entity_summary = {
        entity: {
            "claims": len(scores),
            "faithfulness": _mean([score.get("faithfulness") for score in scores]),
            "spatial_support": _mean(
                [score.get("spatial_support") for score in scores]
            ),
            "temporal_support": _mean(
                [score.get("temporal_support") for score in scores]
            ),
            "statuses": dict(Counter(score["status"] for score in scores)),
        }
        for entity, scores in sorted(by_entity.items())
    }
    return {
        "captions": len(rows),
        "scenes": len({row["sample_id"] for row in rows}),
        "elapsed_seconds": elapsed,
        "by_model": model_summary,
        "by_entity": entity_summary,
        "claim_statuses": dict(statuses),
    }


def _pairwise_deltas(
    rows_by_mode: dict[EvidenceMode, list[dict[str, Any]]],
) -> dict[str, Any]:
    baseline_mode = EvidenceMode.FULL_TARGET
    if baseline_mode not in rows_by_mode:
        return {}
    baseline = {
        (row["sample_id"], row["model"]): row["score"]
        for row in rows_by_mode[baseline_mode]
    }
    output: dict[str, Any] = {}
    for mode, rows in rows_by_mode.items():
        if mode == baseline_mode:
            continue
        by_model: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(
            list
        )
        for row in rows:
            key = (row["sample_id"], row["model"])
            if key in baseline:
                by_model[row["model"]].append((row["score"], baseline[key]))
        output[mode.value] = {
            model: {
                metric: _mean(
                    [
                        current[metric] - base[metric]
                        for current, base in pairs
                        if current.get(metric) is not None
                        and base.get(metric) is not None
                    ]
                )
                for metric in METRICS
            }
            for model, pairs in sorted(by_model.items())
        }
    return output


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# MGA 证据构造对照实验",
        "",
        f"- 场景数：{summary['scenes']}",
        f"- Caption 数：{summary['captions']}",
        f"- 输入分割缓存：`{summary['segmentation_run_dir']}`",
        "",
        "## 方法定义",
        "",
    ]
    for mode in summary["modes"]:
        lines.append(f"- **{mode}**：{summary['mode_descriptions'][mode]}")

    lines.extend(
        [
            "",
            "## 分模型结果",
            "",
            "| 模式 | 模型 | Faithfulness | Coverage | Temporal | Overall | Unverifiable |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, mode_summary in summary["results"].items():
        for model, values in mode_summary["by_model"].items():
            lines.append(
                f"| {mode} | {model} | {_fmt(values['faithfulness'])} | "
                f"{_fmt(values['coverage'])} | {_fmt(values['temporal'])} | "
                f"{_fmt(values['overall'])} | {_fmt(values['unverifiable_rate'])} |"
            )

    lines.extend(
        [
            "",
            "## 相对 Full target 的平均变化",
            "",
            "| 模式 | 模型 | ΔFaithfulness | ΔCoverage | ΔTemporal | ΔOverall | "
            "ΔUnverifiable |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, models in summary["pairwise_delta_vs_full_target"].items():
        for model, values in models.items():
            lines.append(
                f"| {mode} | {model} | {_fmt(values['faithfulness'])} | "
                f"{_fmt(values['coverage'])} | {_fmt(values['temporal'])} | "
                f"{_fmt(values['overall'])} | {_fmt(values['unverifiable_rate'])} |"
            )

    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- MaskLabelOnly 的高分只说明 Caption 提到了真实掩膜中存在的类别；"
            "它不验证 add/remove/modify 方向、位置、数量或静态上下文。",
            "- GT-ROI gated 使用真实 ROI 门控，是带有 oracle 信息的乐观对照，"
            "不能作为实际部署结果。",
            "- Temporal delta 对 SegEarth 的跨时相配准和掩膜稳定性更敏感；"
            "下降既可能来自 Caption 错误，也可能来自分割抖动。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    modes = [EvidenceMode(value) for value in args.modes]
    records = load_manifest(args.manifest)
    scene_order, scenes = _segmentation_index(args.segmentation_run_dir)
    if args.max_scenes is not None:
        scene_order = scene_order[: args.max_scenes]
    selected_ids = set(scene_order)
    records = [record for record in records if record.sample_id in selected_ids]
    if not records:
        raise ValueError("No manifest records overlap the cached segmentation scenes")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    label_cache: dict[str, np.ndarray] = {}
    grounding_mask_cache: dict[str, np.ndarray] = {}
    evidence_cache: dict[tuple[str, str], dict[str, GroundingEvidence]] = {}
    for record in records:
        key = (record.sample_id, record.model)
        evidence_cache[key] = _evidence_for_record(
            record, scenes[record.sample_id], grounding_mask_cache
        )

    rows_by_mode: dict[EvidenceMode, list[dict[str, Any]]] = {}
    summaries: dict[str, Any] = {}
    for mode in modes:
        started = time.perf_counter()
        scorer = MGAV2Scorer(MGAV2Config(evidence_mode=mode))
        rows = []
        for record in records:
            if record.change_mask not in label_cache:
                label_cache[record.change_mask] = load_label_mask(record.change_mask)
            evidence = (
                {}
                if mode == EvidenceMode.MASK_LABEL_ONLY
                else evidence_cache[(record.sample_id, record.model)]
            )
            score = scorer.score(record, label_cache[record.change_mask], evidence)
            rows.append(
                {
                    "evidence_mode": mode.value,
                    "sample_id": record.sample_id,
                    "model": record.model,
                    "dataset": record.dataset,
                    "caption": record.caption,
                    "claims": [claim.to_dict() for claim in record.claims],
                    "score": score.to_dict(),
                }
            )
        elapsed = time.perf_counter() - started
        rows_by_mode[mode] = rows
        summaries[mode.value] = _summarize_mode(rows, elapsed)
        write_jsonl(args.output_dir / f"{mode.value}.jsonl", rows)

    summary = {
        "manifest": str(args.manifest.resolve()),
        "segmentation_run_dir": str(args.segmentation_run_dir.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "scenes": len(selected_ids),
        "captions": len(records),
        "modes": [mode.value for mode in modes],
        "mode_descriptions": {
            mode.value: MODE_DESCRIPTIONS[mode] for mode in modes
        },
        "results": summaries,
        "pairwise_delta_vs_full_target": _pairwise_deltas(rows_by_mode),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(args.output_dir / "report.zh-CN.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
