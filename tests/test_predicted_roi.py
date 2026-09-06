from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from mga.predicted_roi import (
    apply_gate_floor,
    build_roi,
    load_probability_map,
    otsu_threshold,
    probability_map,
    relation_mask,
    rgb_feature_difference,
    roi_quality,
    soft_relation_score,
    threshold_probability,
)


def test_probability_map_handles_uint_image_and_resize() -> None:
    value = np.asarray([[0, 255], [128, 64]], dtype=np.uint8)
    result = probability_map(value, shape=(4, 4))
    assert result.shape == (4, 4)
    assert float(result.min()) >= 0.0
    assert float(result.max()) <= 1.0
    assert result[-1, -1] == pytest.approx(64 / 255, abs=0.08)


def test_otsu_and_quantile_separate_bimodal_probability() -> None:
    value = np.zeros((10, 10), dtype=np.float32)
    value[:, 5:] = 1.0
    threshold = otsu_threshold(value)
    binary, reported = threshold_probability(value, method="otsu")
    assert 0.0 <= threshold < 1.0
    assert reported == pytest.approx(threshold)
    assert not binary[:, :5].any()
    assert binary[:, 5:].all()

    quantile_binary, quantile_threshold = threshold_probability(
        value,
        method="quantile",
        quantile=0.49,
    )
    assert quantile_threshold == pytest.approx(0.0)
    assert quantile_binary[:, 5:].all()


def test_rgb_feature_difference_localises_changed_patch() -> None:
    pre = np.zeros((20, 20, 3), dtype=np.uint8)
    post = pre.copy()
    post[2:8, 3:9] = 255
    difference = rgb_feature_difference(pre, post, blur_radius=0.0)
    assert difference.shape == (20, 20)
    assert float(difference[3:7, 4:8].mean()) > 0.95
    assert float(difference[12:, 12:].max()) == 0.0


def test_external_npz_prediction_and_predicted_cd_gate(tmp_path) -> None:
    prediction = np.zeros((8, 8), dtype=np.float32)
    prediction[:4, :4] = 0.9
    prediction_path = tmp_path / "prediction.npz"
    np.savez_compressed(prediction_path, probability=prediction)
    loaded = load_probability_map(prediction_path, array_key="probability")
    assert np.array_equal(loaded, prediction)

    image = np.zeros((8, 8, 3), dtype=np.uint8)
    result = build_roi(
        "predicted_cd_roi",
        shape=(8, 8),
        pre_image=image,
        post_image=image,
        predicted_path=prediction_path,
        gate_floor=0.1,
    )
    assert result.metadata["source"] == "external_change_detector"
    assert float(result.probability[:4, :4].mean()) == pytest.approx(1.0)
    assert float(result.probability[4:, 4:].mean()) == pytest.approx(0.1)


def test_build_roi_modes_keep_oracle_and_no_roi_auditable() -> None:
    oracle = np.zeros((10, 10), dtype=bool)
    oracle[2:5, 2:5] = True
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    oracle_result = build_roi(
        "oracle_gt_roi",
        shape=oracle.shape,
        oracle_change=oracle,
    )
    no_roi_result = build_roi(
        "no_roi",
        shape=oracle.shape,
    )
    assert np.array_equal(oracle_result.probability.astype(bool), oracle)
    assert oracle_result.metadata["source"] == "reference_change"
    assert no_roi_result.probability.all()
    assert no_roi_result.metadata["source"] == "constant_one"

    feature = build_roi(
        "feature_difference_roi",
        shape=oracle.shape,
        pre_image=image,
        post_image=image,
        gate_floor=0.2,
    )
    assert np.allclose(feature.probability, 0.2)


def test_relation_mask_and_soft_gate_are_separate() -> None:
    source_pre = np.zeros((16, 16), dtype=bool)
    source_pre[2:6, 2:6] = True
    source_post = np.zeros_like(source_pre)
    target_pre = np.zeros_like(source_pre)
    target_post = source_pre.copy()
    relation = relation_mask(
        source_masks=(source_pre, source_post),
        target_masks=(target_pre, target_post),
        location="upper-left",
        temporal_radius=0,
        relation_radius=0,
    )
    assert relation is not None
    assert np.array_equal(relation, source_pre)
    supported = np.zeros_like(source_pre, dtype=np.float32)
    supported[2:6, 2:6] = 0.8
    assert soft_relation_score(relation, supported) == pytest.approx(0.8)
    assert soft_relation_score(None, supported) is None
    assert soft_relation_score(np.zeros_like(source_pre), supported) == 0.0


def test_roi_quality_reports_pixel_diagnostics() -> None:
    reference = np.zeros((6, 6), dtype=bool)
    reference[:3, :3] = True
    perfect = roi_quality(reference.astype(np.float32), reference)
    assert perfect["iou"] == 1.0
    assert perfect["precision"] == 1.0
    assert perfect["recall"] == 1.0
    assert perfect["f1"] == 1.0
    assert perfect["mae"] == 0.0


def test_gate_floor_validates_range() -> None:
    value = np.asarray([[0.0, 1.0]], dtype=np.float32)
    assert np.allclose(apply_gate_floor(value, 0.1), [[0.1, 1.0]])
    with pytest.raises(ValueError, match="gate floor"):
        apply_gate_floor(value, 1.0)


def test_image_prediction_loader(tmp_path) -> None:
    path = tmp_path / "mask.png"
    Image.fromarray(np.asarray([[0, 255]], dtype=np.uint8)).save(path)
    loaded = load_probability_map(path)
    assert np.allclose(loaded, [[0.0, 1.0]])
