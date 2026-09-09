"""Decode RGB semantic maps into stable integer class-id masks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


def load_rgb_palette(path: str | Path) -> dict[int, tuple[tuple[int, int, int], ...]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    palette = {}
    for class_id, colors in raw.items():
        normalized = tuple(tuple(int(channel) for channel in color) for color in colors)
        if any(len(color) != 3 for color in normalized):
            raise ValueError(f"Palette class {class_id} contains a non-RGB color")
        palette[int(class_id)] = normalized
    return palette


def decode_rgb_label(
    value: np.ndarray,
    palette: dict[int, tuple[tuple[int, int, int], ...]],
    *,
    unknown_class: int | None = None,
) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 2:
        return array.astype(np.uint8, copy=False)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError(f"Expected HxWx3 RGB label, got shape {array.shape}")
    rgb = array[:, :, :3]
    decoded = np.full(rgb.shape[:2], -1, dtype=np.int16)
    for class_id, colors in palette.items():
        for color in colors:
            decoded[np.all(rgb == np.asarray(color, dtype=rgb.dtype), axis=2)] = class_id
    unknown_mask = decoded < 0
    if unknown_mask.any():
        colors, counts = np.unique(rgb[unknown_mask].reshape(-1, 3), axis=0, return_counts=True)
        unknown = [
            {"rgb": color.tolist(), "pixels": int(count)}
            for color, count in zip(colors, counts, strict=True)
        ]
        if unknown_class is None:
            raise ValueError(f"RGB label contains unknown colors: {unknown[:12]}")
        decoded[unknown_mask] = int(unknown_class)
    if decoded.max(initial=0) > 255:
        raise ValueError("Decoded class id exceeds uint8 range")
    return decoded.astype(np.uint8)


def decode_label_file(
    source: str | Path,
    output: str | Path,
    palette: dict[int, tuple[tuple[int, int, int], ...]],
    *,
    unknown_class: int | None = None,
) -> None:
    with Image.open(source) as image:
        value = np.asarray(image.convert("RGB"))
    decoded = decode_rgb_label(value, palette, unknown_class=unknown_class)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(decoded, mode="L").save(target, optimize=True)
