"""Mask loading and metric primitives without heavyweight vision dependencies."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from PIL import Image


def load_label_mask(path: str | Path) -> np.ndarray:
    path = Path(path)
    if path.suffix.lower() == ".npy":
        mask = np.load(path, allow_pickle=False)
    else:
        with Image.open(path) as image:
            mask = np.asarray(image)
    if mask.ndim == 3:
        if mask.shape[2] == 1:
            mask = mask[..., 0]
        else:
            raise ValueError(
                f"Expected a single-channel label mask, got {mask.shape} from {path}. "
                "Convert RGB color masks to class IDs explicitly."
            )
    if mask.ndim != 2:
        raise ValueError(f"Expected a 2D mask, got {mask.shape} from {path}")
    return mask


def select_change_mask(label_mask: np.ndarray, labels: Iterable[int] = ()) -> np.ndarray:
    labels = tuple(int(label) for label in labels)
    if labels:
        return np.isin(label_mask, labels)
    return label_mask != 0


def as_bool_mask(mask: np.ndarray | None, shape: tuple[int, int] | None = None) -> np.ndarray:
    if mask is None:
        if shape is None:
            raise ValueError("shape is required when mask is None")
        return np.zeros(shape, dtype=bool)
    value = np.asarray(mask, dtype=bool)
    if value.ndim != 2:
        raise ValueError(f"Expected a 2D support mask, got {value.shape}")
    if shape is not None and value.shape != shape:
        raise ValueError(f"Mask shape mismatch: expected {shape}, got {value.shape}")
    return value


def intersection_over_union(left: np.ndarray, right: np.ndarray) -> float:
    left, right = _paired(left, right)
    union = np.logical_or(left, right).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(left, right).sum() / union)


def support_precision(support: np.ndarray, target: np.ndarray) -> float:
    support, target = _paired(support, target)
    denominator = support.sum()
    if denominator == 0:
        return 0.0
    return float(np.logical_and(support, target).sum() / denominator)


def non_overlap_ratio(support: np.ndarray, target: np.ndarray) -> float:
    return 1.0 - support_precision(support, target)


def temporal_novelty(target_time: np.ndarray, other_time: np.ndarray, change: np.ndarray) -> float:
    target_time, other_time = _paired(target_time, other_time)
    target_time, change = _paired(target_time, change)
    supported = np.logical_and(target_time, change)
    denominator = supported.sum()
    if denominator == 0:
        return 0.0
    persistent = np.logical_and(supported, other_time).sum()
    return float(1.0 - persistent / denominator)


def temporal_difference(pre: np.ndarray, post: np.ndarray, change: np.ndarray) -> float:
    pre, post = _paired(pre, post)
    pre, change = _paired(pre, change)
    union = np.logical_and(np.logical_or(pre, post), change)
    denominator = union.sum()
    if denominator == 0:
        return 0.0
    difference = np.logical_and(np.logical_xor(pre, post), change).sum()
    return float(difference / denominator)


def connected_components(mask: np.ndarray, min_area: int = 1) -> list[np.ndarray]:
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError(f"Expected a 2D mask, got {mask.shape}")
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[np.ndarray] = []

    for row, col in zip(*np.nonzero(mask), strict=False):
        if visited[row, col]:
            continue
        queue: deque[tuple[int, int]] = deque([(int(row), int(col))])
        visited[row, col] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            current_row, current_col = queue.popleft()
            pixels.append((current_row, current_col))
            for next_row, next_col in (
                (current_row - 1, current_col),
                (current_row + 1, current_col),
                (current_row, current_col - 1),
                (current_row, current_col + 1),
            ):
                if (
                    0 <= next_row < height
                    and 0 <= next_col < width
                    and mask[next_row, next_col]
                    and not visited[next_row, next_col]
                ):
                    visited[next_row, next_col] = True
                    queue.append((next_row, next_col))
        if len(pixels) >= min_area:
            component = np.zeros_like(mask, dtype=bool)
            rows, cols = zip(*pixels, strict=True)
            component[np.asarray(rows), np.asarray(cols)] = True
            components.append(component)
    return components


def filter_intersecting_components(support: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Legacy v1 filtering retained only for controlled comparison."""
    support, target = _paired(support, target)
    filtered = np.zeros_like(support, dtype=bool)
    for component in connected_components(support):
        if np.logical_and(component, target).any():
            filtered |= component
    return filtered


def component_coverage(
    target: np.ndarray,
    support: np.ndarray,
    overlap_threshold: float = 0.10,
    min_component_area: int = 4,
) -> float:
    target, support = _paired(target, support)
    components = connected_components(target, min_area=min_component_area)
    if not components:
        return 1.0
    covered = 0
    for component in components:
        overlap = np.logical_and(component, support).sum() / component.sum()
        covered += int(overlap >= overlap_threshold)
    return float(covered / len(components))


def _paired(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    left = np.asarray(left, dtype=bool)
    right = np.asarray(right, dtype=bool)
    if left.shape != right.shape:
        raise ValueError(f"Mask shape mismatch: {left.shape} != {right.shape}")
    if left.ndim != 2:
        raise ValueError(f"Expected 2D masks, got {left.shape}")
    return left, right
