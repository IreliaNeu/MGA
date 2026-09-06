"""Change-ROI construction and soft gating for annotation-free MGA variants.

The functions in this module deliberately separate entity grounding from change
localisation.  A caller first builds a source-to-target relation mask from the
bi-temporal entity masks, then selects one of four interchangeable ROI sources:

``oracle_gt_roi``
    A semantic-label difference or reference change mask.  This is an oracle
    upper bound and must not be described as annotation-free.
``predicted_cd_roi``
    A change probability/mask supplied by an independent external detector.
    This mode never falls back to a feature-difference proxy.
``feature_difference_roi``
    A continuous, robustly normalised RGB difference map.
``no_roi``
    An all-one gate that tests whether change localisation is needed at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from mga.evidence_routing import binary_dilate, location_mask

ROI_MODES = (
    "oracle_gt_roi",
    "predicted_cd_roi",
    "feature_difference_roi",
    "no_roi",
)


@dataclass(frozen=True)
class ROIResult:
    """A spatial change gate and audit metadata for one image pair."""

    mode: str
    probability: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


def probability_map(
    value: np.ndarray,
    *,
    shape: tuple[int, int] | None = None,
) -> np.ndarray:
    """Convert masks, uint images, probabilities, or logits to ``[0, 1]``.

    Arbitrary floating-point maps are robustly min-max normalised with the 1st
    and 99th percentiles.  This makes external detector logits usable without
    assuming a model-specific calibration, while preserving already calibrated
    probabilities unchanged.
    """

    array = np.asarray(value)
    if array.ndim == 3:
        if array.shape[2] == 1:
            array = array[..., 0]
        else:
            array = array.astype(np.float32).mean(axis=2)
    if array.ndim != 2:
        raise ValueError(f"Expected a two-dimensional ROI map, got {array.shape}")
    array = array.astype(np.float32, copy=False)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    minimum = float(array.min(initial=0.0))
    maximum = float(array.max(initial=0.0))
    if minimum >= 0.0 and maximum <= 1.0:
        result = array.copy()
    elif minimum >= 0.0 and maximum <= 255.0:
        result = array / 255.0
    else:
        low, high = (float(item) for item in np.quantile(array, (0.01, 0.99)))
        if high <= low:
            result = np.zeros_like(array, dtype=np.float32)
        else:
            result = np.clip((array - low) / (high - low), 0.0, 1.0)
    if shape is not None and result.shape != shape:
        result = resize_probability(result, shape)
    return np.clip(result, 0.0, 1.0).astype(np.float32, copy=False)


def resize_probability(value: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Resize a probability map to ``(height, width)`` with bilinear sampling."""

    height, width = shape
    if height <= 0 or width <= 0:
        raise ValueError(f"Invalid target shape: {shape}")
    image = Image.fromarray(np.asarray(value, dtype=np.float32), mode="F")
    resized = image.resize((width, height), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32)


def load_probability_map(
    path: str | Path,
    *,
    shape: tuple[int, int] | None = None,
    array_key: str | None = None,
) -> np.ndarray:
    """Load a detector prediction from an image, ``.npy``, or ``.npz`` file."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Predicted ROI does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".npy":
        value = np.load(path, allow_pickle=False)
    elif suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            candidates = (
                (array_key,) if array_key else ()
            ) + ("probability", "prob", "change", "mask", "prediction", "arr_0")
            selected = next((key for key in candidates if key and key in archive), None)
            if selected is None:
                raise KeyError(
                    f"Cannot find an ROI array in {path}; available keys: "
                    f"{', '.join(archive.files)}"
                )
            value = archive[selected]
    else:
        with Image.open(path) as image:
            value = np.asarray(image)
    return probability_map(value, shape=shape)


def rgb_feature_difference(
    pre_image: str | Path | np.ndarray,
    post_image: str | Path | np.ndarray,
    *,
    shape: tuple[int, int] | None = None,
    blur_radius: float = 1.0,
    low_quantile: float = 0.05,
    high_quantile: float = 0.995,
) -> np.ndarray:
    """Build a robust continuous change map from aligned RGB image pairs."""

    if not 0.0 <= low_quantile < high_quantile <= 1.0:
        raise ValueError("Expected 0 <= low_quantile < high_quantile <= 1")
    pre = _load_rgb(pre_image)
    post = _load_rgb(post_image)
    if post.shape != pre.shape:
        post_image_value = Image.fromarray(post)
        post = np.asarray(
            post_image_value.resize(
                (pre.shape[1], pre.shape[0]),
                resample=Image.Resampling.BILINEAR,
            )
        )
    difference = np.abs(pre.astype(np.float32) - post.astype(np.float32)).mean(axis=2)
    if blur_radius > 0:
        difference_image = Image.fromarray(
            np.rint(np.clip(difference, 0.0, 255.0)).astype(np.uint8),
            mode="L",
        )
        blurred = difference_image.filter(
            ImageFilter.GaussianBlur(radius=float(blur_radius))
        )
        difference = np.asarray(blurred, dtype=np.float32)
    low, high = (
        float(item)
        for item in np.quantile(difference, (low_quantile, high_quantile))
    )
    if high <= low:
        result = np.zeros_like(difference, dtype=np.float32)
    else:
        result = np.clip((difference - low) / (high - low), 0.0, 1.0)
    if shape is not None and result.shape != shape:
        result = resize_probability(result, shape)
    return result.astype(np.float32, copy=False)


def otsu_threshold(value: np.ndarray, bins: int = 256) -> float:
    """Return Otsu's threshold for a probability map using NumPy only."""

    array = probability_map(value).ravel()
    if not array.size or float(array.max()) <= float(array.min()):
        return 1.0
    histogram, edges = np.histogram(array, bins=bins, range=(0.0, 1.0))
    histogram = histogram.astype(np.float64)
    centres = (edges[:-1] + edges[1:]) / 2.0
    cumulative_weight = np.cumsum(histogram)
    cumulative_mean = np.cumsum(histogram * centres)
    total_weight = cumulative_weight[-1]
    total_mean = cumulative_mean[-1]
    background = cumulative_weight
    foreground = total_weight - cumulative_weight
    valid = np.logical_and(background > 0, foreground > 0)
    variance = np.full_like(centres, -1.0, dtype=np.float64)
    numerator = (total_mean * background - cumulative_mean) ** 2
    variance[valid] = numerator[valid] / (background[valid] * foreground[valid])
    return float(centres[int(np.argmax(variance))])


def threshold_probability(
    value: np.ndarray,
    *,
    method: str = "otsu",
    quantile: float = 0.90,
    fixed_threshold: float = 0.50,
) -> tuple[np.ndarray, float]:
    """Binarise a probability map with Otsu or a foreground quantile."""

    probability = probability_map(value)
    if method == "otsu":
        threshold = otsu_threshold(probability)
    elif method == "quantile":
        if not 0.0 < quantile < 1.0:
            raise ValueError("quantile must lie strictly between 0 and 1")
        threshold = float(np.quantile(probability, quantile))
    elif method == "fixed":
        if not 0.0 < fixed_threshold < 1.0:
            raise ValueError("fixed_threshold must lie strictly between 0 and 1")
        threshold = float(fixed_threshold)
    else:
        raise ValueError(f"Unknown threshold method: {method}")
    return (probability > threshold).astype(np.float32), threshold


def apply_gate_floor(value: np.ndarray, floor: float) -> np.ndarray:
    """Turn a hard exclusion mask into a soft attention gate."""

    if not 0.0 <= floor < 1.0:
        raise ValueError("gate floor must satisfy 0 <= floor < 1")
    probability = probability_map(value)
    return floor + (1.0 - floor) * probability


def build_roi(
    mode: str,
    *,
    shape: tuple[int, int],
    pre_image: str | Path | np.ndarray | None = None,
    post_image: str | Path | np.ndarray | None = None,
    oracle_change: np.ndarray | None = None,
    predicted_path: str | Path | None = None,
    predicted_array_key: str | None = None,
    threshold_method: str = "otsu",
    threshold_quantile: float = 0.90,
    fixed_threshold: float = 0.50,
    gate_floor: float = 0.10,
    blur_radius: float = 1.0,
) -> ROIResult:
    """Construct one of the four audit-ready ROI variants."""

    if mode not in ROI_MODES:
        raise ValueError(f"Unknown ROI mode: {mode}")
    if mode == "oracle_gt_roi":
        if oracle_change is None:
            raise ValueError("oracle_gt_roi requires oracle_change")
        probability = probability_map(oracle_change, shape=shape)
        metadata: dict[str, Any] = {"source": "reference_change", "gate_floor": 0.0}
    elif mode == "feature_difference_roi":
        if pre_image is None or post_image is None:
            raise ValueError("feature_difference_roi requires pre_image and post_image")
        feature_difference = rgb_feature_difference(
            pre_image,
            post_image,
            shape=shape,
            blur_radius=blur_radius,
        )
        probability = apply_gate_floor(feature_difference, gate_floor)
        metadata = {
            "source": "rgb_feature_difference",
            "gate_floor": gate_floor,
            "blur_radius": blur_radius,
        }
    elif mode == "predicted_cd_roi":
        if predicted_path is None:
            raise ValueError(
                "predicted_cd_roi requires an independent detector prediction; "
                "use feature_difference_roi for the non-learned weak baseline"
            )
        prediction = load_probability_map(
            predicted_path,
            shape=shape,
            array_key=predicted_array_key,
        )
        binary, threshold = threshold_probability(
            prediction,
            method=threshold_method,
            quantile=threshold_quantile,
            fixed_threshold=fixed_threshold,
        )
        probability = apply_gate_floor(binary, gate_floor)
        metadata = {
            "source": "external_change_detector",
            "prediction_path": str(predicted_path),
            "threshold_method": threshold_method,
            "threshold": threshold,
            "threshold_quantile": threshold_quantile,
            "fixed_threshold": fixed_threshold,
            "gate_floor": gate_floor,
        }
    else:
        probability = np.ones(shape, dtype=np.float32)
        metadata = {"source": "constant_one", "gate_floor": 1.0}
    probability = probability_map(probability, shape=shape)
    metadata = {
        **metadata,
        "foreground_fraction_at_0.5": float((probability >= 0.5).mean()),
        "mean_probability": float(probability.mean()),
    }
    return ROIResult(mode=mode, probability=probability, metadata=metadata)


def relation_mask(
    *,
    source_masks: tuple[np.ndarray, np.ndarray] | None,
    target_masks: tuple[np.ndarray, np.ndarray] | None,
    location: str = "",
    temporal_radius: int = 2,
    relation_radius: int = 3,
) -> np.ndarray | None:
    """Construct the source-remove/target-add spatial relation independently of ROI."""

    if source_masks is None or target_masks is None:
        return None
    source_pre, source_post = (
        np.asarray(item, dtype=bool) for item in source_masks
    )
    target_pre, target_post = (
        np.asarray(item, dtype=bool) for item in target_masks
    )
    shape = source_pre.shape
    if source_pre.ndim != 2 or any(
        item.shape != shape for item in (source_post, target_pre, target_post)
    ):
        return None
    source_removed = np.logical_and(
        source_pre,
        ~binary_dilate(source_post, radius=temporal_radius),
    )
    target_added = np.logical_and(
        target_post,
        ~binary_dilate(target_pre, radius=temporal_radius),
    )
    relation = np.logical_and(
        binary_dilate(source_removed, radius=relation_radius),
        binary_dilate(target_added, radius=relation_radius),
    )
    relation &= location_mask(location, shape)
    return relation


def soft_relation_score(
    relation: np.ndarray | None,
    roi_probability: np.ndarray,
) -> float | None:
    """Average ROI support over a candidate relation; abstain only if evidence is missing."""

    if relation is None:
        return None
    relation = np.asarray(relation, dtype=bool)
    roi = probability_map(roi_probability, shape=relation.shape)
    if not relation.any():
        return 0.0
    return float(roi[relation].mean())


def roi_quality(
    prediction: np.ndarray,
    reference: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Pixel-level quality diagnostics for a predicted change ROI."""

    probability = probability_map(prediction)
    target = np.asarray(reference, dtype=bool)
    if probability.shape != target.shape:
        probability = resize_probability(probability, target.shape)
    binary = probability >= threshold
    true_positive = int(np.logical_and(binary, target).sum())
    false_positive = int(np.logical_and(binary, ~target).sum())
    false_negative = int(np.logical_and(~binary, target).sum())
    union = true_positive + false_positive + false_negative
    precision = true_positive / (true_positive + false_positive) if binary.any() else 0.0
    recall = true_positive / int(target.sum()) if target.any() else float(not binary.any())
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )
    return {
        "iou": true_positive / union if union else 1.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mae": float(np.abs(probability - target.astype(np.float32)).mean()),
        "predicted_fraction": float(binary.mean()),
        "reference_fraction": float(target.mean()),
    }


def _load_rgb(value: str | Path | np.ndarray) -> np.ndarray:
    if isinstance(value, (str, Path)):
        with Image.open(value) as image:
            return np.asarray(image.convert("RGB"))
    array = np.asarray(value)
    if array.ndim == 2:
        array = np.repeat(array[..., None], 3, axis=2)
    if array.ndim != 3 or array.shape[2] not in {3, 4}:
        raise ValueError(f"Expected an RGB image, got {array.shape}")
    return array[..., :3].astype(np.uint8, copy=False)
