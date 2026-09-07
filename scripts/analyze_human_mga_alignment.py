"""Relate scene-level human judgments to MGA evidence-mode ablations."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from mga.io import read_jsonl
from mga.models import EvidenceMode

MODEL_ORDER = ("Change-Agent", "Draft", "Guided")
PREFERENCE_MODEL = {
    "Change": "Change-Agent",
    "Draft": "Draft",
    "Refined": "Guided",
}
METRIC_DIRECTIONS = {
    "faithfulness": 1.0,
    "coverage": 1.0,
    "temporal": 1.0,
    "overall": 1.0,
    "verifiability": 1.0,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-eval-jsonl", required=True, type=Path)
    parser.add_argument("--ablation-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def _normalize_caption(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return re.sub(r"[\s.]+$", "", normalized)


def _rankdata(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=float)
    start = 0
    while start < len(array):
        end = start + 1
        while end < len(array) and array[order[end]] == array[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    return ranks


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3:
        return None
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    if left_array.std() == 0 or right_array.std() == 0:
        return None
    return float(np.corrcoef(left_array, right_array)[0, 1])


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = _rankdata(scores)
    positive_rank_sum = float(
        sum(rank for rank, label in zip(ranks, labels, strict=True) if label == 1)
    )
    return (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)


def _balanced_accuracy(
    labels: list[int], scores: list[float], threshold: float = 0.60
) -> float | None:
    true_positive = true_negative = positive = negative = 0
    for label, score in zip(labels, scores, strict=True):
        prediction = int(score >= threshold)
        if label:
            positive += 1
            true_positive += int(prediction == 1)
        else:
            negative += 1
            true_negative += int(prediction == 0)
    if positive == 0 or negative == 0:
        return None
    return float((true_positive / positive + true_negative / negative) / 2)


def _score_value(score: dict[str, Any], metric: str) -> float | None:
    if metric == "verifiability":
        value = score.get("unverifiable_rate")
        return None if value is None else 1.0 - float(value)
    value = score.get(metric)
    return None if value is None else float(value)


def _metric_validity(
    human_rows: list[dict[str, Any]],
    auto_rows: dict[tuple[str, str], dict[str, Any]],
    metric: str,
    allowed_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    labels: list[int] = []
    scores: list[float] = []
    for human in human_rows:
        sample_id = human["sample_id"]
        for model in MODEL_ORDER:
            key = (sample_id, model)
            if key not in allowed_keys:
                continue
            auto = auto_rows.get(key)
            if auto is None:
                continue
            value = _score_value(auto["score"], metric)
            if value is None:
                continue
            labels.append(int(human["validity"][model]))
            scores.append(METRIC_DIRECTIONS[metric] * value)
    return {
        "n": len(scores),
        "positive": sum(labels),
        "point_biserial_r": _correlation(labels, scores),
        "spearman_rho": _correlation(
            list(_rankdata([float(value) for value in labels])),
            list(_rankdata(scores)),
        ),
        "roc_auc": _auc(labels, scores),
        "balanced_accuracy_at_0_60": _balanced_accuracy(labels, scores),
    }


def _preference_accuracy(
    human_rows: list[dict[str, Any]],
    auto_rows: dict[tuple[str, str], dict[str, Any]],
    metric: str,
    allowed_scene_ids: set[str],
) -> dict[str, Any]:
    correct = 0
    evaluated = 0
    ties = 0
    fractional_credit = 0.0
    unique_correct = 0
    unique_evaluated = 0
    for human in human_rows:
        if human["sample_id"] not in allowed_scene_ids:
            continue
        preferred = PREFERENCE_MODEL.get(human["human_preference"])
        if preferred is None:
            continue
        candidates = []
        for model in MODEL_ORDER:
            auto = auto_rows.get((human["sample_id"], model))
            if auto is None:
                continue
            value = _score_value(auto["score"], metric)
            if value is not None:
                candidates.append((model, value))
        if not candidates:
            continue
        best_value = max(value for _model, value in candidates)
        winners = {
            model
            for model, value in candidates
            if math.isclose(value, best_value, rel_tol=1e-9, abs_tol=1e-12)
        }
        evaluated += 1
        ties += int(len(winners) > 1)
        correct += int(preferred in winners)
        fractional_credit += (
            1.0 / len(winners) if preferred in winners else 0.0
        )
        if len(winners) == 1:
            unique_evaluated += 1
            unique_correct += int(preferred in winners)
    return {
        "n": evaluated,
        "correct": correct,
        "accuracy_tie_as_correct": correct / evaluated if evaluated else None,
        "accuracy_fractional_tie_credit": (
            fractional_credit / evaluated if evaluated else None
        ),
        "automatic_ties": ties,
        "unique_winner_n": unique_evaluated,
        "unique_winner_correct": unique_correct,
        "unique_winner_accuracy": (
            unique_correct / unique_evaluated if unique_evaluated else None
        ),
    }


def _human_summary(human_rows: list[dict[str, Any]]) -> dict[str, Any]:
    validity = {
        model: {
            "positive": sum(int(row["validity"][model]) for row in human_rows),
            "rate": sum(int(row["validity"][model]) for row in human_rows)
            / len(human_rows),
        }
        for model in MODEL_ORDER
    }
    preferences = Counter(
        row.get("human_preference") or "NoMajority" for row in human_rows
    )
    llm = Counter(row.get("llm_judge") or "Missing" for row in human_rows)
    preference_rows = [
        row
        for row in human_rows
        if (row.get("human_preference") or "NoMajority") != "NoMajority"
    ]
    preference_count = len(preference_rows)
    agreement = (
        sum(
            row["human_preference"] == row["llm_judge"]
            for row in preference_rows
        )
        / preference_count
        if preference_count
        else None
    )
    paired_preferences = Counter(
        row["human_preference"] for row in preference_rows
    )
    paired_llm = Counter(row["llm_judge"] for row in preference_rows)
    labels = sorted(set(paired_preferences) | set(paired_llm))
    chance = (
        sum(paired_preferences[label] * paired_llm[label] for label in labels)
        / preference_count**2
        if preference_count
        else None
    )
    kappa = (
        (agreement - chance) / (1 - chance)
        if agreement is not None and chance is not None and chance < 1
        else None
    )
    return {
        "scenes": len(human_rows),
        "validity": validity,
        "refined_extra_correct_detail": {
            "positive": sum(row["refined_extra_correct_detail"] for row in human_rows),
            "rate": sum(row["refined_extra_correct_detail"] for row in human_rows)
            / len(human_rows),
        },
        "gt_mask_missing_localized_object": {
            "positive": sum(
                row["gt_mask_missing_localized_object"] for row in human_rows
            ),
            "rate": sum(
                row["gt_mask_missing_localized_object"] for row in human_rows
            )
            / len(human_rows),
        },
        "human_preference": dict(preferences),
        "llm_judge": dict(llm),
        "human_llm_n": preference_count,
        "human_llm_exact_agreement": agreement,
        "human_llm_cohen_kappa": kappa,
    }


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    human = summary["human"]
    lines = [
        "# 人工评价与 MGA 证据模式对齐分析",
        "",
        f"- 场景数：{human['scenes']}",
        f"- 自动结果匹配的 caption：{summary['caption_alignment']['matched']}/"
        f"{summary['caption_alignment']['total']}",
        f"- 人工与 LLM-as-Judge 完全一致率："
        f"{human['human_llm_exact_agreement']:.3f}",
        f"- Cohen's κ：{_fmt(human['human_llm_cohen_kappa'])}",
        "",
        "## 人工题项概况",
        "",
        "| 题项 | 正例 | 比例 |",
        "|---|---:|---:|",
    ]
    for model, values in human["validity"].items():
        lines.append(
            f"| {model} 变化描述成立 | {values['positive']} | {values['rate']:.3f} |"
        )
    extra = human["refined_extra_correct_detail"]
    missing = human["gt_mask_missing_localized_object"]
    lines.append(f"| Refined 新增正确细节 | {extra['positive']} | {extra['rate']:.3f} |")
    lines.append(
        f"| 正确定位但 GT Mask 未标 | {missing['positive']} | {missing['rate']:.3f} |"
    )

    lines.extend(
        [
            "",
            "## 自动指标对人工“变化描述成立”的效度",
            "",
            "| 模式 | 指标 | n | Point-biserial r | Spearman ρ | ROC-AUC | "
            "Balanced Acc@0.60 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, metrics in summary["validity_alignment"].items():
        for metric, values in metrics.items():
            lines.append(
                f"| {mode} | {metric} | {values['n']} | "
                f"{_fmt(values['point_biserial_r'])} | "
                f"{_fmt(values['spearman_rho'])} | {_fmt(values['roc_auc'])} | "
                f"{_fmt(values['balanced_accuracy_at_0_60'])} |"
            )

    lines.extend(
        [
            "",
            "## 自动指标选择人工偏好描述的能力",
            "",
            "| 模式 | 指标 | n | 分摊并列 Top-1 | 自动并列 | 唯一赢家 n | "
            "唯一赢家准确率 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, metrics in summary["preference_alignment"].items():
        for metric, values in metrics.items():
            lines.append(
                f"| {mode} | {metric} | {values['n']} | "
                f"{_fmt(values['accuracy_fractional_tie_credit'])} | "
                f"{values['automatic_ties']} | {values['unique_winner_n']} | "
                f"{_fmt(values['unique_winner_accuracy'])} |"
            )

    lines.extend(
        [
            "",
            "## 使用限制",
            "",
            "- 此脚本读取已汇总的人类标签，不从输入行数推断评审人数；"
            "评审一致性应依据原始逐评审记录单独计算。",
            "- F/G/H 是场景级二值题，不能区分实体、变化方向、位置、数量与属性错误。",
            "- K 是主观偏好，不等价于事实正确；且题项没有拆分流畅性、信息量与事实性。",
            "- MaskLabelOnly 的 Overall 与含 Temporal 的模式发生了可用权重重归一化，"
            "不能只比较 Overall 绝对值。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    human_rows = list(read_jsonl(args.human_eval_jsonl))
    if not human_rows:
        raise ValueError("Human evaluation file is empty")
    for row in human_rows:
        row["sample_id"] = str(row["sample_id"]).lower()

    auto_by_mode: dict[EvidenceMode, dict[tuple[str, str], dict[str, Any]]] = {}
    for mode in EvidenceMode:
        path = args.ablation_dir / f"{mode.value}.jsonl"
        if not path.is_file():
            continue
        rows = list(read_jsonl(path))
        auto_by_mode[mode] = {
            (str(row["sample_id"]).lower(), str(row["model"])): row for row in rows
        }

    caption_total = 0
    caption_matched = 0
    matched_keys: set[tuple[str, str]] = set()
    mismatches = []
    reference_auto = auto_by_mode[EvidenceMode.FULL_TARGET]
    for human in human_rows:
        for model in MODEL_ORDER:
            caption_total += 1
            key = (human["sample_id"], model)
            auto = reference_auto.get(key)
            if auto is None:
                mismatches.append({"sample_id": key[0], "model": model, "reason": "missing"})
                continue
            if _normalize_caption(human["captions"][model]) == _normalize_caption(
                auto["caption"]
            ):
                caption_matched += 1
                matched_keys.add(key)
            else:
                mismatches.append(
                    {
                        "sample_id": key[0],
                        "model": model,
                        "reason": "caption_mismatch",
                        "human_caption": human["captions"][model],
                        "manifest_caption": auto["caption"],
                    }
                )
    complete_scene_ids = {
        human["sample_id"]
        for human in human_rows
        if all((human["sample_id"], model) in matched_keys for model in MODEL_ORDER)
    }

    validity_alignment = {}
    preference_alignment = {}
    for mode, auto_rows in auto_by_mode.items():
        validity_alignment[mode.value] = {
            metric: _metric_validity(human_rows, auto_rows, metric, matched_keys)
            for metric in METRIC_DIRECTIONS
        }
        preference_alignment[mode.value] = {
            metric: _preference_accuracy(
                human_rows, auto_rows, metric, complete_scene_ids
            )
            for metric in METRIC_DIRECTIONS
        }

    summary = {
        "human_eval_jsonl": str(args.human_eval_jsonl.resolve()),
        "ablation_dir": str(args.ablation_dir.resolve()),
        "human": _human_summary(human_rows),
        "caption_alignment": {
            "total": caption_total,
            "matched": caption_matched,
            "complete_scenes": len(complete_scene_ids),
            "mismatches": mismatches,
        },
        "validity_alignment": validity_alignment,
        "preference_alignment": preference_alignment,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "human_alignment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(args.output_dir / "human_alignment_report.zh-CN.md", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
