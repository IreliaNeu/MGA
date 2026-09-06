from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_script():
    path = Path(__file__).parents[1] / "scripts" / "analyze_roi_calibration.py"
    spec = importlib.util.spec_from_file_location("analyze_roi_calibration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calibration = load_script()


def test_choose_threshold_calibrates_low_magnitude_scores() -> None:
    pairs = [(True, 0.20), (True, 0.18), (False, 0.05), (False, 0.02)]
    threshold, result = calibration.choose_threshold(pairs)
    assert 0.05 < threshold <= 0.18
    assert result["balanced_accuracy"] == 1.0
    assert result["false_support_rate"] == 0.0


def test_group_split_is_deterministic_and_group_disjoint() -> None:
    values = {
        sample_id: calibration.group_split(sample_id, seed=17, dev_fraction=0.5)
        for sample_id in ("a", "b", "c", "d")
    }
    assert values == {
        sample_id: calibration.group_split(sample_id, seed=17, dev_fraction=0.5)
        for sample_id in values
    }


def test_evaluate_preserves_missing_scores_as_unverifiable() -> None:
    rows = [
        {"is_factually_correct": True, "scores": {"m": 0.8}},
        {"is_factually_correct": False, "scores": {"m": 0.1}},
        {"is_factually_correct": True, "scores": {"m": None}},
    ]
    result = calibration.evaluate(rows, "m", 0.5)
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["unverifiable_rate"] == pytest.approx(1 / 3)
    assert result["balanced_accuracy"] == 1.0
