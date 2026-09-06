from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_script(name: str):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selective = load_script("analyze_selective_prediction")


def test_selective_curve_reports_abstention_risk_fsr_and_precision() -> None:
    entries = [
        {"item_id": "p1", "label": True, "score": 0.95, "confidence": 0.45},
        {"item_id": "n1", "label": False, "score": 0.05, "confidence": 0.45},
        {"item_id": "n2", "label": False, "score": 0.70, "confidence": 0.20},
        {"item_id": "p2", "label": True, "score": None, "confidence": None},
    ]

    summary, curve = selective.risk_coverage_analysis(
        entries,
        target_coverages=(0.5, 0.75, 1.0),
    )

    assert summary["evaluation_coverage"] == 0.75
    assert summary["explicit_abstention_rate"] == 0.25
    assert curve[0]["coverage"] == 0.5  # confidence tie retained as a group
    assert curve[0]["risk"] == 0.0
    assert curve[0]["false_support_rate"] == 0.0
    assert curve[0]["supported_precision"] == 1.0
    assert curve[-1]["risk"] == pytest.approx(1 / 3)
    assert curve[-1]["false_support_rate"] == 0.5
    assert curve[-1]["supported_precision"] == 0.5
    assert summary["target_coverages"][-1]["attainable"] is False
    assert summary["aurc"] == pytest.approx(1 / 9)


def test_prepare_entries_auto_confidence_and_missing_score() -> None:
    rows = [
        {
            "item_id": "a",
            "sample_id": "scene-a",
            "is_factually_correct": True,
            "scores": {"hybrid": 0.8},
        },
        {
            "item_id": "b",
            "sample_id": "scene-b",
            "is_factually_correct": False,
            "scores": {"hybrid": None},
        },
    ]
    by_method = selective.prepare_entries(
        rows,
        method_paths={"hybrid": "scores.hybrid"},
        confidence_paths={},
        label_field="is_factually_correct",
        id_field="item_id",
        group_field="sample_id",
        threshold=0.5,
    )

    assert by_method["hybrid"][0]["confidence"] == pytest.approx(0.3)
    assert by_method["hybrid"][1]["score"] is None
    assert by_method["hybrid"][1]["confidence"] is None
