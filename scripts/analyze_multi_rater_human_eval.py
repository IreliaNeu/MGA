"""Analyze three first-round human-evaluation workbooks without modifying them."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
DOC_REL_NS = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
}
QUESTION_COLUMNS = {
    "F": "change_agent_correct",
    "G": "draft_correct",
    "H": "refined_correct",
    "I": "refined_extra_correct_detail",
    "J": "gt_mask_missing_localized_object",
}
VALIDITY_MODELS = {
    "Change-Agent": "change_agent_correct",
    "Draft": "draft_correct",
    "Guided": "refined_correct",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbooks", nargs=3, required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--majority-jsonl", required=True, type=Path)
    return parser


def _cell_column(reference: str) -> str:
    return re.match(r"[A-Z]+", reference).group(0)  # type: ignore[union-attr]


def _read_first_sheet(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", NS):
                shared.append("".join(node.text or "" for node in item.findall(".//a:t", NS)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find("a:sheets/a:sheet", NS)
        if first_sheet is None:
            raise ValueError(f"{path}: workbook has no sheets")
        relation_id = first_sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = None
        for relation in relationships.findall("r:Relationship", REL_NS):
            if relation.attrib["Id"] == relation_id:
                target = relation.attrib["Target"]
                break
        if target is None:
            raise ValueError(f"{path}: cannot resolve first worksheet")
        sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        sheet = ET.fromstring(archive.read(sheet_path))

        rows: list[dict[str, Any]] = []
        for row in sheet.findall("a:sheetData/a:row", NS):
            row_number = int(row.attrib["r"])
            values: dict[str, Any] = {"_row": row_number}
            for cell in row.findall("a:c", NS):
                column = _cell_column(cell.attrib["r"])
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", NS)
                inline = cell.find("a:is", NS)
                if cell_type == "inlineStr" and inline is not None:
                    value: Any = "".join(
                        node.text or "" for node in inline.findall(".//a:t", NS)
                    )
                elif value_node is None:
                    value = None
                elif cell_type == "s":
                    value = shared[int(value_node.text or "0")]
                elif cell_type in {"str", "e"}:
                    value = value_node.text or ""
                else:
                    raw = value_node.text or ""
                    try:
                        numeric = float(raw)
                        value = int(numeric) if numeric.is_integer() else numeric
                    except ValueError:
                        value = raw
                values[column] = value
            rows.append(values)
    return rows


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_choice(value: Any) -> str:
    text = _clean_text(value)
    aliases = {
        "Change-Agent": "Change",
        "Change Agent": "Change",
        "Guided": "Refined",
        "Refine": "Refined",
    }
    return aliases.get(text, text)


def _binary(value: Any, path: Path, row: int, column: str) -> int | None:
    if value is None or value == "":
        return None
    if value in (0, 0.0, "0", False):
        return 0
    if value in (1, 1.0, "1", True):
        return 1
    raise ValueError(f"{path}: {column}{row} must be binary, got {value!r}")


def _load_workbook(path: Path) -> list[dict[str, Any]]:
    source_rows = _read_first_sheet(path)
    data_rows = [row for row in source_rows if 2 <= row["_row"] <= 51]
    if len(data_rows) != 50:
        raise ValueError(f"{path}: expected rows 2:51, got {len(data_rows)}")
    records = []
    for row in data_rows:
        record = {
            "index": int(row["A"]),
            "sample_id": _clean_text(row["B"]),
            "captions": {
                "Change-Agent": _clean_text(row["C"]),
                "Draft": _clean_text(row["D"]),
                "Guided": _clean_text(row["E"]),
            },
            "human_preference": _normalize_choice(row.get("K")),
            "llm_judge": _normalize_choice(row.get("L")),
            "_source_row": row["_row"],
        }
        for column, name in QUESTION_COLUMNS.items():
            record[name] = _binary(row.get(column), path, row["_row"], column)
        records.append(record)
    return records


def _cohen_kappa(left: list[Any], right: list[Any]) -> dict[str, Any]:
    if len(left) != len(right) or not left:
        raise ValueError("Cohen kappa requires two equally sized non-empty lists")
    labels = sorted(set(left) | set(right), key=str)
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    chance = sum(left_counts[label] * right_counts[label] for label in labels) / (
        len(left) ** 2
    )
    kappa = None if math.isclose(chance, 1.0) else (observed - chance) / (1 - chance)
    return {"agreement": observed, "chance": chance, "kappa": kappa}


def _fleiss_kappa(ratings: list[list[Any]]) -> dict[str, Any]:
    if not ratings or any(len(item) != len(ratings[0]) for item in ratings):
        raise ValueError("Fleiss kappa requires equal non-empty rater counts")
    n = len(ratings[0])
    categories = sorted({value for item in ratings for value in item}, key=str)
    per_item_agreement = []
    totals = Counter()
    for item in ratings:
        counts = Counter(item)
        totals.update(item)
        per_item_agreement.append(
            (sum(counts[category] ** 2 for category in categories) - n) / (n * (n - 1))
        )
    observed = statistics.mean(per_item_agreement)
    category_rates = {
        category: totals[category] / (len(ratings) * n) for category in categories
    }
    chance = sum(rate**2 for rate in category_rates.values())
    kappa = None if math.isclose(chance, 1.0) else (observed - chance) / (1 - chance)
    exact = sum(len(set(item)) == 1 for item in ratings) / len(ratings)
    return {
        "items": len(ratings),
        "raters": n,
        "exact_agreement": exact,
        "mean_pair_agreement": observed,
        "chance": chance,
        "kappa": kappa,
        "category_rates": {str(key): value for key, value in category_rates.items()},
    }


def _majority(values: Iterable[Any]) -> Any:
    counts = Counter(value for value in values if value not in (None, ""))
    if not counts:
        return None
    value, count = counts.most_common(1)[0]
    return value if count >= 2 else None


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _analyze(raters: list[list[dict[str, Any]]], paths: list[Path]) -> dict[str, Any]:
    reference = raters[0]
    for rater_index, records in enumerate(raters[1:], start=2):
        for row_index, (expected, actual) in enumerate(
            zip(reference, records, strict=True), start=2
        ):
            if expected["sample_id"] != actual["sample_id"]:
                raise ValueError(
                    f"{paths[rater_index - 1]} row {row_index}: sample ID mismatch"
                )
            if expected["captions"] != actual["captions"]:
                raise ValueError(
                    f"{paths[rater_index - 1]} row {row_index}: caption mismatch"
                )

    per_rater = {}
    for path, rows in zip(paths, raters, strict=True):
        binary_positive = {}
        for question in QUESTION_COLUMNS.values():
            observed = [row[question] for row in rows if row[question] is not None]
            binary_positive[question] = {
                "n": len(observed),
                "missing": len(rows) - len(observed),
                "count": sum(observed),
                "rate": sum(observed) / len(observed) if observed else None,
            }
        per_rater[path.name] = {
            "binary_positive": binary_positive,
            "human_preference": dict(
                Counter(row["human_preference"] or "Missing" for row in rows)
            ),
            "llm_judge": dict(Counter(row["llm_judge"] or "Missing" for row in rows)),
        }

    questions = {}
    for question in QUESTION_COLUMNS.values():
        all_item_ratings = [
            [rater[item_index][question] for rater in raters]
            for item_index in range(len(reference))
        ]
        item_ratings = [
            item for item in all_item_ratings if all(value is not None for value in item)
        ]
        pairwise = {}
        kappas = []
        for left_index, right_index in ((0, 1), (0, 2), (1, 2)):
            pairs = [
                (left[question], right[question])
                for left, right in zip(
                    raters[left_index], raters[right_index], strict=True
                )
                if left[question] is not None and right[question] is not None
            ]
            result = _cohen_kappa(
                [left for left, _right in pairs],
                [right for _left, right in pairs],
            )
            result["n"] = len(pairs)
            pairwise[f"r{left_index + 1}_r{right_index + 1}"] = result
            if result["kappa"] is not None:
                kappas.append(result["kappa"])
        questions[question] = {
            "fleiss": _fleiss_kappa(item_ratings),
            "complete_items": len(item_ratings),
            "items_with_missing": len(all_item_ratings) - len(item_ratings),
            "pairwise": pairwise,
            "mean_pairwise_kappa": statistics.mean(kappas) if kappas else None,
        }

    all_preference_items = [
        [rater[item_index]["human_preference"] for rater in raters]
        for item_index in range(len(reference))
    ]
    preference_items = [
        item for item in all_preference_items if all(value for value in item)
    ]
    preference_pairwise = {}
    preference_kappas = []
    for left_index, right_index in ((0, 1), (0, 2), (1, 2)):
        pairs = [
            (left["human_preference"], right["human_preference"])
            for left, right in zip(
                raters[left_index], raters[right_index], strict=True
            )
            if left["human_preference"] and right["human_preference"]
        ]
        result = _cohen_kappa(
            [left for left, _right in pairs],
            [right for _left, right in pairs],
        )
        result["n"] = len(pairs)
        preference_pairwise[f"r{left_index + 1}_r{right_index + 1}"] = result
        if result["kappa"] is not None:
            preference_kappas.append(result["kappa"])

    majority_rows = []
    for item_index, base in enumerate(reference):
        majority_row = {
            "index": base["index"],
            "sample_id": base["sample_id"],
            "captions": base["captions"],
            "validity": {
                model: _majority(
                    rater[item_index][question]
                    for rater in raters
                )
                for model, question in VALIDITY_MODELS.items()
            },
            "refined_extra_correct_detail": _majority(
                rater[item_index]["refined_extra_correct_detail"] for rater in raters
            ),
            "gt_mask_missing_localized_object": _majority(
                rater[item_index]["gt_mask_missing_localized_object"]
                for rater in raters
            ),
            "human_preference": _majority(
                rater[item_index]["human_preference"] for rater in raters
            )
            or "NoMajority",
            "llm_judge": base["llm_judge"],
        }
        majority_rows.append(majority_row)

    valid_preferences = [
        row
        for row in majority_rows
        if row["human_preference"] != "NoMajority" and row["llm_judge"]
    ]
    human_llm = _cohen_kappa(
        [row["human_preference"] for row in valid_preferences],
        [row["llm_judge"] for row in valid_preferences],
    )
    def binary_summary(values: list[int | None]) -> dict[str, Any]:
        observed = [value for value in values if value is not None]
        return {
            "n": len(observed),
            "missing": len(values) - len(observed),
            "count": sum(observed),
            "rate": sum(observed) / len(observed) if observed else None,
        }

    majority_summary = {
        "validity": {
            model: binary_summary([row["validity"][model] for row in majority_rows])
            for model in VALIDITY_MODELS
        },
        "refined_extra_correct_detail": binary_summary(
            [row["refined_extra_correct_detail"] for row in majority_rows]
        ),
        "gt_mask_missing_localized_object": binary_summary(
            [row["gt_mask_missing_localized_object"] for row in majority_rows]
        ),
        "human_preference": dict(
            Counter(row["human_preference"] or "NoMajority" for row in majority_rows)
        ),
        "human_llm": {"n": len(valid_preferences), **human_llm},
    }
    return {
        "workbooks": [str(path.resolve()) for path in paths],
        "scenes": len(reference),
        "per_rater": per_rater,
        "questions": questions,
        "preference": {
            "fleiss": _fleiss_kappa(preference_items),
            "complete_items": len(preference_items),
            "items_with_missing": len(all_preference_items) - len(preference_items),
            "pairwise": preference_pairwise,
            "mean_pairwise_kappa": (
                statistics.mean(preference_kappas) if preference_kappas else None
            ),
        },
        "majority": majority_summary,
        "_majority_rows": majority_rows,
    }


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    majority = summary["majority"]
    lines = [
        "# 三评审人工评价一致性分析",
        "",
        f"- 场景数：{summary['scenes']}；评审人数：3。",
        "- 所有统计均重新读取第 2–51 行原始标注；未采用工作簿底部手工汇总。",
        "",
        "## 逐题一致性",
        "",
        "| 题目 | 三人完全一致率 | Fleiss κ | 平均两两 Cohen κ |",
        "|---|---:|---:|---:|",
    ]
    labels = {
        "change_agent_correct": "Change-Agent 描述正确",
        "draft_correct": "Draft 描述正确",
        "refined_correct": "Refined 描述正确",
        "refined_extra_correct_detail": "Refined 新增细节正确",
        "gt_mask_missing_localized_object": "正确实体未被 GT 掩膜覆盖",
    }
    for question, result in summary["questions"].items():
        lines.append(
            f"| {labels[question]} | {result['fleiss']['exact_agreement']:.3f} | "
            f"{_fmt(result['fleiss']['kappa'])} | "
            f"{_fmt(result['mean_pairwise_kappa'])} |"
        )
    preference = summary["preference"]
    lines.extend(
        [
            f"| 三描述偏好 | {preference['fleiss']['exact_agreement']:.3f} | "
            f"{_fmt(preference['fleiss']['kappa'])} | "
            f"{_fmt(preference['mean_pairwise_kappa'])} |",
            "",
            "## 三人多数票",
            "",
            "| 指标 | 正例数 | 比例 |",
            "|---|---:|---:|",
        ]
    )
    for model, result in majority["validity"].items():
        lines.append(f"| {model} 描述正确 | {result['count']} | {result['rate']:.3f} |")
    for name, label in (
        ("refined_extra_correct_detail", "Refined 新增细节正确"),
        ("gt_mask_missing_localized_object", "正确实体未被 GT 掩膜覆盖"),
    ):
        result = majority[name]
        lines.append(f"| {label} | {result['count']} | {result['rate']:.3f} |")
    lines.extend(
        [
            "",
            f"- 多数票偏好分布：{majority['human_preference']}。",
            f"- 多数票人工偏好与 LLM-as-Judge：n={majority['human_llm']['n']}，"
            f"完全一致率={majority['human_llm']['agreement']:.3f}，"
            f"Cohen κ={_fmt(majority['human_llm']['kappa'])}。",
            "",
            "## 解读原则",
            "",
            "- κ 衡量扣除随机一致后的可靠性；完全一致率用于直观展示，但不能替代 κ。",
            "- 多数票用于后续 MGA 对齐分析；若三人各选一个偏好，则记为 "
            "NoMajority 并从偏好一致性计算中排除。",
            "- 样本量仅 50，结果适合方法诊断和消融实验，不应表述为稳定的人群层面结论。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    paths = [path.resolve() for path in args.workbooks]
    raters = [_load_workbook(path) for path in paths]
    summary = _analyze(raters, paths)
    majority_rows = summary.pop("_majority_rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.majority_jsonl.parent.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_report(args.output_dir / "report.zh-CN.md", summary)
    with args.majority_jsonl.open("w", encoding="utf-8") as handle:
        for row in majority_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
